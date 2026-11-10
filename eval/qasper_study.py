"""CPU retrieval experiments on the frozen QASPER release.

The official test split is protected by an explicit opt-in flag. Results include
per-question rankings and run provenance; no answer-generation judge is used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import re
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/frozen/qasper_manifest.json"
DATA_DIR = ROOT / "data/downloads/qasper"
RESULTS = ROOT / "results"
TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
EMBEDDING_MODEL = "intfloat/e5-small-v2"
EMBEDDING_REVISION = "ffb93f3bd4047442299a41ebb6fa998a38507c52"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"


@dataclass(frozen=True)
class Passage:
    id: str
    paper_id: str
    text: str
    section: str
    kind: str


@dataclass(frozen=True)
class Question:
    id: str
    paper_id: str
    text: str
    gold_evidence: tuple[str, ...]
    unanswerable: bool


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).lower()
    return " ".join(TOKEN_RE.findall(value))


def tokenize(value: str) -> list[str]:
    return TOKEN_RE.findall(value.lower())


def _passages(row: Any) -> list[Passage]:
    result: list[Passage] = []
    full_text = row["full_text"]
    sections = _list(full_text.get("section_name"))
    paragraph_groups = _list(full_text.get("paragraphs"))
    for section_index, section in enumerate(sections):
        group = paragraph_groups[section_index] if section_index < len(paragraph_groups) else []
        for paragraph_index, paragraph in enumerate(_list(group)):
            if isinstance(paragraph, str) and paragraph.strip():
                result.append(Passage(
                    id=f"{row['id']}:p{section_index}:{paragraph_index}",
                    paper_id=str(row["id"]), text=paragraph.strip(),
                    section=str(section), kind="paragraph",
                ))

    tables = row.get("figures_and_tables") or {}
    captions = _list(tables.get("caption")) if isinstance(tables, dict) else []
    for index, caption in enumerate(captions):
        if not isinstance(caption, str) or not caption.strip():
            continue
        start = caption.lstrip().lower()
        kind = "table" if start.startswith(("table", "tab.")) else "figure" if start.startswith(("figure", "fig.")) else "caption"
        result.append(Passage(
            id=f"{row['id']}:c{index}", paper_id=str(row["id"]),
            text=caption.strip(), section="figure_or_table_caption", kind=kind,
        ))
    return result


def _questions(row: Any) -> list[Question]:
    qas = row["qas"]
    questions = _list(qas.get("question"))
    question_ids = _list(qas.get("question_id"))
    answer_groups = _list(qas.get("answers"))
    result: list[Question] = []
    for index, text in enumerate(questions):
        answers = answer_groups[index] if index < len(answer_groups) else {}
        annotations = _list(answers.get("answer")) if isinstance(answers, dict) else []
        flags: list[bool] = []
        evidence: set[str] = set()
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            flags.append(bool(annotation.get("unanswerable", False)))
            highlighted = _list(annotation.get("highlighted_evidence"))
            raw_evidence = highlighted or _list(annotation.get("evidence"))
            evidence.update(str(item).strip() for item in raw_evidence if str(item).strip())
        qid = str(question_ids[index]) if index < len(question_ids) else f"{row['id']}:{index}"
        result.append(Question(
            id=qid, paper_id=str(row["id"]), text=str(text),
            gold_evidence=tuple(sorted(evidence)),
            unanswerable=bool(flags) and all(flags),
        ))
    return result


def verify_data(split: str) -> tuple[Path, dict[str, Any]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = DATA_DIR / f"{split}.parquet"
    expected = manifest["files"][split]
    if not target.exists():
        raise FileNotFoundError(f"Dataset missing: {target}; run scripts/download_qasper.py")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != expected["sha256"]:
        raise ValueError(f"Dataset hash mismatch for {split}: {digest} != {expected['sha256']}")
    return target, manifest


def _rank_metrics(ranked: list[str], relevant: set[str], k: int) -> dict[str, float]:
    if not relevant:
        return {"recall": float("nan"), "mrr": float("nan"), "ndcg": float("nan")}
    top = ranked[:k]
    hits = [1 if item in relevant else 0 for item in top]
    recall = sum(hits) / len(relevant)
    reciprocal_rank = next((1.0 / (i + 1) for i, hit in enumerate(hits) if hit), 0.0)
    dcg = sum(hit / np.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1.0 / np.log2(i + 2) for i in range(min(len(relevant), k)))
    return {"recall": recall, "mrr": reciprocal_rank, "ndcg": dcg / ideal if ideal else 0.0}


def _paired_inference(records: list[dict[str, Any]], first: str, second: str,
                      subset: str | None = None, n_resamples: int = 10_000) -> dict[str, Any]:
    pairs = []
    for record in records:
        if not record.get("mappable") or first not in record.get("metrics", {}) or second not in record.get("metrics", {}):
            continue
        if subset == "table_figure" and not ({"table_reference", "figure_reference"} & set(record.get("gold_types", []))):
            continue
        if subset and subset != "table_figure" and subset not in record.get("gold_types", []):
            continue
        a = record["metrics"][first]["recall@10"]
        b = record["metrics"][second]["recall@10"]
        pairs.append(a - b)
    if not pairs:
        return {"n": 0, "mean_difference": None, "bootstrap_95_ci": None, "paired_randomization_p": None}
    differences = np.asarray(pairs, dtype=np.float64)
    rng = np.random.default_rng(0)
    samples = rng.choice(differences, size=(n_resamples, len(differences)), replace=True).mean(axis=1)
    observed = float(differences.mean())
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_resamples, len(differences)))
    null_means = (signs * differences).mean(axis=1)
    p_value = (int(np.count_nonzero(np.abs(null_means) >= abs(observed))) + 1) / (n_resamples + 1)
    return {
        "n": len(differences), "mean_difference": observed,
        "bootstrap_95_ci": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
        "paired_randomization_p": p_value, "bootstrap_resamples": n_resamples, "seed": 0,
    }


def _rrf(rankings: list[list[str]], constant: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (constant + rank)
    return sorted(scores, key=lambda item: (-scores[item], item))


class EmbeddingDiskCache:
    """Content-addressed persistent cache for deterministic retrieval vectors."""

    def __init__(self, model_id: str, revision: str | None) -> None:
        cache_path = ROOT / "cache" / "experiment_embeddings.sqlite3"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cache_path)
        self.model_key = f"{model_id}@{revision or 'unversioned'}|normalized-f32|maxlen512"
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, dim INTEGER NOT NULL, vector BLOB NOT NULL)"
        )
        self.db.commit()
        self.hits = 0
        self.misses = 0

    def key(self, text: str) -> str:
        return hashlib.sha256((self.model_key + "\0" + text).encode("utf-8")).hexdigest()

    def get(self, text: str) -> np.ndarray | None:
        row = self.db.execute("SELECT dim, vector FROM vectors WHERE key=?", (self.key(text),)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        return np.frombuffer(row[1], dtype=np.float32, count=row[0]).copy()

    def put(self, text: str, vector: np.ndarray) -> None:
        vector = np.asarray(vector, dtype=np.float32)
        self.db.execute(
            "INSERT OR REPLACE INTO vectors(key, dim, vector) VALUES(?,?,?)",
            (self.key(text), int(vector.size), vector.tobytes()),
        )

    def flush(self) -> None:
        self.db.commit()

    def close(self) -> None:
        self.db.commit()
        self.db.close()


def _run_id() -> tuple[str, str]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), commit


def evaluate(split: str, systems: list[str], top_k: int, candidate_k: int,
             embedding_model_id: str = EMBEDDING_MODEL, limit: int | None = None) -> Path:
    dataset_path, manifest = verify_data(split)
    if split == "test":
        if not ALLOW_TEST:
            raise PermissionError("Test split requires --allow-test after validation choices are frozen.")
        if limit is not None:
            raise ValueError("The registered experiment evaluates the complete official test split; --limit is development-only.")
        expected_commit = manifest.get("test_protocol_commit")
        current_commit = _run_id()[1]
        if expected_commit and expected_commit != current_commit:
            raise RuntimeError(f"Test protocol commit mismatch: expected {expected_commit}, got {current_commit}")

    frame = pd.read_parquet(dataset_path)
    paper_rows = {str(row["id"]): row for _, row in frame.iterrows()}
    passage_by_paper = {paper_id: _passages(row) for paper_id, row in paper_rows.items()}
    tokenized_by_paper = {
        paper_id: [tokenize(passage.text) for passage in passages]
        for paper_id, passages in passage_by_paper.items()
    }
    bm25_by_paper = {
        paper_id: BM25Okapi(tokenized)
        for paper_id, tokenized in tokenized_by_paper.items()
        if tokenized
    }
    questions = [question for row in paper_rows.values() for question in _questions(row)]
    questions.sort(key=lambda question: question.id)
    if limit is not None:
        questions = questions[:limit]

    embedding_model = None
    cross_encoder = None
    model_load_start = time.perf_counter()
    if any(name in systems for name in ("dense", "hybrid", "rerank", "mmr", "structure")):
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        revision = EMBEDDING_REVISION if embedding_model_id == EMBEDDING_MODEL else None
        embedding_model = SentenceTransformer(embedding_model_id, revision=revision, device="cpu")
    if any(name in systems for name in ("rerank", "mmr", "structure")):
        from sentence_transformers import CrossEncoder
        cross_encoder = CrossEncoder(RERANKER_MODEL, revision=RERANKER_REVISION, device="cpu")
    model_load_seconds = time.perf_counter() - model_load_start

    embedding_cache: dict[str, np.ndarray] = {}
    vector_cache = EmbeddingDiskCache(embedding_model_id, EMBEDDING_REVISION if embedding_model_id == EMBEDDING_MODEL else None) if embedding_model else None
    records: list[dict[str, Any]] = []
    counts = {"papers": len(paper_rows), "questions": len(questions), "answerable": 0,
              "unanswerable": 0, "mappable": 0, "unmappable": 0}
    start = time.perf_counter()
    stage_seconds = {name: 0.0 for name in (
        "bm25_scoring", "embedding_cache_and_encode", "dense_scoring",
        "cross_encoder_scoring", "mmr_selection", "structure_ordering",
    )}
    peak_rss_bytes = 0
    try:
        import psutil
        process = psutil.Process()
        peak_rss_bytes = process.memory_info().rss
    except ImportError:
        process = None
    for question in questions:
        passages = passage_by_paper[question.paper_id]
        if question.unanswerable:
            counts["unanswerable"] += 1
            records.append({"question_id": question.id, "paper_id": question.paper_id,
                            "question": question.text, "answerable": False})
            continue
        counts["answerable"] += 1
        normalized_gold = {normalize(text) for text in question.gold_evidence if normalize(text)}
        relevant = {
            passage.id for passage in passages
            if any(gold in normalize(passage.text) for gold in normalized_gold)
        }
        if not relevant:
            counts["unmappable"] += 1
            records.append({"question_id": question.id, "paper_id": question.paper_id,
                            "question": question.text, "answerable": True, "mappable": False,
                            "gold_evidence_text": list(question.gold_evidence)})
            continue
        counts["mappable"] += 1
        bm25 = bm25_by_paper[question.paper_id]
        stage_start = time.perf_counter()
        bm25_scores = np.asarray(bm25.get_scores(tokenize(question.text)))
        bm25_order = np.argsort(-bm25_scores, kind="stable")
        bm25_ranked = [passages[int(i)].id for i in bm25_order]
        stage_seconds["bm25_scoring"] += time.perf_counter() - stage_start

        dense_ranked: list[str] = []
        dense_query_vector: np.ndarray | None = None
        if embedding_model is not None:
            stage_start = time.perf_counter()
            missing = [p for p in passages if p.id not in embedding_cache]
            still_missing: list[Passage] = []
            for passage in missing:
                vector = vector_cache.get(f"passage: {passage.text}") if vector_cache else None
                if vector is None:
                    still_missing.append(passage)
                else:
                    embedding_cache[passage.id] = vector
            if still_missing:
                inputs = [f"passage: {p.text}" for p in still_missing]
                vectors = embedding_model.encode(inputs, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
                for passage, vector in zip(still_missing, vectors):
                    vector = np.asarray(vector, dtype=np.float32)
                    embedding_cache[passage.id] = vector
                    vector_cache.put(f"passage: {passage.text}", vector)
                vector_cache.flush()
            query_text = f"query: {question.text}"
            dense_query_vector = vector_cache.get(query_text) if vector_cache else None
            if dense_query_vector is None:
                dense_query_vector = embedding_model.encode(query_text, normalize_embeddings=True, show_progress_bar=False)
                if vector_cache:
                    vector_cache.put(query_text, np.asarray(dense_query_vector, dtype=np.float32))
                    vector_cache.flush()
            stage_seconds["embedding_cache_and_encode"] += time.perf_counter() - stage_start
            stage_start = time.perf_counter()
            dense_scores = np.asarray([float(np.dot(embedding_cache[p.id], dense_query_vector)) for p in passages])
            dense_order = np.argsort(-dense_scores, kind="stable")
            dense_ranked = [passages[int(i)].id for i in dense_order]
            stage_seconds["dense_scoring"] += time.perf_counter() - stage_start

        rankings: dict[str, list[str]] = {"bm25": bm25_ranked}
        if dense_ranked:
            rankings["dense"] = dense_ranked
            rankings["hybrid"] = _rrf([bm25_ranked, dense_ranked])
        chosen: dict[str, list[str]] = {}
        for system in systems:
            if system in rankings:
                chosen[system] = rankings[system]
            elif system in ("rerank", "mmr", "structure") and dense_ranked:
                candidates = _rrf([bm25_ranked, dense_ranked])[:candidate_k]
                if system in ("rerank", "mmr", "structure") and cross_encoder is not None:
                    lookup = {p.id: p.text for p in passages}
                    stage_start = time.perf_counter()
                    scores = cross_encoder.predict([[question.text, lookup[pid]] for pid in candidates], show_progress_bar=False)
                    stage_seconds["cross_encoder_scoring"] += time.perf_counter() - stage_start
                    reranked = [
                        pid for _, pid in sorted(
                            zip(scores, candidates), key=lambda pair: (-float(pair[0]), candidates.index(pair[1]))
                        )
                    ]
                    if system == "rerank":
                        chosen[system] = reranked
                    else:
                        # MMR over the same cross-encoder candidate pool; relevance and
                        # redundancy are cosine scores from the fixed dense encoder.
                        qsim = {pid: float(np.dot(embedding_cache[pid], dense_query_vector)) for pid in candidates}
                        by_rank = {pid: rank for rank, pid in enumerate(reranked)}
                        selected: list[str] = []
                        remaining = set(candidates)
                        stage_start = time.perf_counter()
                        while remaining and len(selected) < len(candidates):
                            best = max(remaining, key=lambda pid: (
                                0.7 * qsim[pid] - 0.3 * max(
                                    (float(np.dot(embedding_cache[pid], embedding_cache[other])) for other in selected),
                                    default=0.0,
                                ),
                                -by_rank[pid], pid,
                            ))
                            selected.append(best)
                            remaining.remove(best)
                        stage_seconds["mmr_selection"] += time.perf_counter() - stage_start
                        if system == "mmr":
                            chosen[system] = selected
                        else:
                            from retrieval.query_analyzer import detect_question_type, score_chunk_for_question
                            question_type = detect_question_type(question.text)["question_type"]
                            lookup = {p.id: p for p in passages}
                            rank_scores = {pid: 1.0 - rank / max(len(selected), 1) for rank, pid in enumerate(selected)}
                            structural_scores = {
                                pid: score_chunk_for_question({
                                    "content": lookup[pid].text,
                                    "metadata": {
                                        "chunk_type": {"table": "TABLE", "figure": "FIGURE"}.get(lookup[pid].kind, "TEXT"),
                                        "section": lookup[pid].section,
                                        "contains_table": lookup[pid].kind == "table",
                                        "contains_figure": lookup[pid].kind == "figure",
                                    },
                                }, question_type)
                                for pid in selected
                            }
                            stage_start = time.perf_counter()
                            chosen[system] = sorted(
                                selected,
                                key=lambda pid: (0.75 * rank_scores[pid] + 0.25 * structural_scores[pid], -by_rank[pid]),
                                reverse=True,
                            )
                            stage_seconds["structure_ordering"] += time.perf_counter() - stage_start
                else:
                    raise RuntimeError(f"System {system!r} requires a dense encoder and cross-encoder")
        metrics = {}
        for name, order in chosen.items():
            at_5 = _rank_metrics(order, relevant, min(5, top_k))
            at_10 = _rank_metrics(order, relevant, top_k)
            metrics[name] = {
                "recall@5": at_5["recall"], "recall@10": at_10["recall"],
                "mrr": at_10["mrr"], "ndcg@10": at_10["ndcg"],
            }
        gold_types = sorted({passage.kind for passage in passages if passage.id in relevant})
        if any(re.search(r"\b(?:TABREF|table\s*\d+|tab\.?\s*\d+)\b", text, re.I) for text in question.gold_evidence):
            gold_types.append("table_reference")
        if any(re.search(r"\b(?:FIGREF|figure\s*\d+|fig\.?\s*\d+)\b", text, re.I) for text in question.gold_evidence):
            gold_types.append("figure_reference")
        records.append({
            "question_id": question.id, "paper_id": question.paper_id,
            "question": question.text, "answerable": True,
            "mappable": True, "gold_passage_ids": sorted(relevant), "gold_types": sorted(set(gold_types)),
            "gold_evidence_text": list(question.gold_evidence),
            "rankings": {name: order[:top_k] for name, order in chosen.items()}, "metrics": metrics,
        })
        if process is not None and len(records) % 50 == 0:
            peak_rss_bytes = max(peak_rss_bytes, process.memory_info().rss)
        if len(records) % 50 == 0:
            print(f"Processed {len(records)}/{len(questions)} validation questions", flush=True)

    duration_s = time.perf_counter() - start
    cache_stats = {"hits": vector_cache.hits, "misses": vector_cache.misses} if vector_cache else None
    if vector_cache:
        vector_cache.close()
    if process is not None:
        peak_rss_bytes = max(peak_rss_bytes, process.memory_info().rss)
    summaries: dict[str, Any] = {}
    for name in systems:
        rows = [r["metrics"][name] for r in records if r.get("mappable") and name in r.get("metrics", {})]
        summaries[name] = {
            key: (float(np.nanmean([r[key] for r in rows])) if rows else None)
            for key in ("recall@5", "recall@10", "mrr", "ndcg@10")
        }
    comparisons = {}
    if "structure" in systems and "mmr" in systems:
        comparisons["structure_minus_mmr_all"] = _paired_inference(records, "structure", "mmr")
        comparisons["structure_minus_mmr_table_figure"] = _paired_inference(
            records, "structure", "mmr", subset="table_figure"
        )
    type_question_count = sum(
        1 for record in records if {"table_reference", "figure_reference"} & set(record.get("gold_types", []))
    )
    type_summaries = {}
    for type_name in ("table_reference", "figure_reference"):
        subset_rows = [r for r in records if r.get("mappable") and type_name in r.get("gold_types", [])]
        type_summaries[type_name] = {
            "n": len(subset_rows),
            "systems": {
                name: (float(np.mean([r["metrics"][name]["recall@10"] for r in subset_rows if name in r["metrics"]]))
                       if subset_rows else None)
                for name in systems
            },
        }
    run_time, commit = _run_id()
    config = {"split": split, "systems": systems, "top_k": top_k, "candidate_k": candidate_k, "limit": limit,
              "embedding_model": embedding_model_id if embedding_model else None,
              "embedding_revision": EMBEDDING_REVISION if embedding_model and embedding_model_id == EMBEDDING_MODEL else None,
              "reranker_model": RERANKER_MODEL if cross_encoder else None,
              "reranker_revision": RERANKER_REVISION if cross_encoder else None,
              "rrf_constant": 60, "mmr_lambda": 0.7, "device": "cpu",
              "python": platform.python_version(), "platform": platform.platform(),
              "cpu_model": platform.processor(),
              "cpu_count": os.cpu_count(),
              "versions": {name: importlib.metadata.version(name) for name in (
                  "numpy", "pandas", "pyarrow", "rank-bm25", "sentence-transformers", "torch", "transformers"
              ) if importlib.metadata.packages_distributions().get(name.replace("-", "_"))}}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    payload = {
        "schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "config": config, "config_sha256": config_hash,
        "dataset_revision": manifest["revision"], "dataset_sha256": manifest["files"][split]["sha256"],
        "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "counts": counts, "elapsed_seconds": duration_s, "summary": summaries, "per_question": records,
        "embedding_cache": cache_stats,
        "model_load_seconds": model_load_seconds,
        "stage_seconds": stage_seconds,
        "peak_rss_bytes_sampled": peak_rss_bytes,
        "paired_comparisons": comparisons,
        "table_figure_evidence_questions": type_question_count,
        "evidence_type_summary": type_summaries,
    }
    outdir = RESULTS / f"{run_time}_{split}_{config_hash[:10]}"
    outdir.mkdir(parents=True, exist_ok=False)
    (outdir / "raw.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return outdir


ALLOW_TEST = False


def main() -> None:
    global ALLOW_TEST
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--systems", default="bm25,dense,hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=40)
    parser.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="Deterministic prefix of question IDs; development smoke tests only")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args()
    ALLOW_TEST = args.allow_test
    systems = [item.strip() for item in args.systems.split(",") if item.strip()]
    allowed = {"bm25", "dense", "hybrid", "rerank", "mmr", "structure"}
    unknown = set(systems) - allowed
    if unknown:
        parser.error(f"unknown system(s): {', '.join(sorted(unknown))}")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    outdir = evaluate(args.split, systems, args.top_k, args.candidate_k, args.embedding_model, args.limit)
    print(outdir.relative_to(ROOT))


if __name__ == "__main__":
    main()
