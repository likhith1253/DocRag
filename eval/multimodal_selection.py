"""Evaluate fixed-budget evidence selection on MMDocRAG and SPIQA.

All outputs contain candidate IDs and scores, not source quote text. The test
runner requires a clean, committed checkout so the evaluator is auditable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/frozen/multimodal_manifest.json"
PROTOCOL = ROOT / "docs/RESEARCH_V2.md"
TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
POLICIES = ("global_bm25", "balanced_bm25", "calibrated_bm25", "text_only", "image_only", "oracle")
BUDGETS = (5, 10, 15, 20)
SEED = 20261110
BOOTSTRAPS = 10_000
SIGN_DRAWS = 10_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def git_value(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def verify_dataset_file(path: Path, record: dict[str, Any]) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing benchmark file {path}; run scripts/download_multimodal_benchmarks.py")
    if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise ValueError(f"Benchmark file does not match frozen manifest: {path}")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def normalized_text(text: str) -> str:
    return " ".join(tokenize(text))


def load_mmdoc(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    unanswerable = 0
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                item = json.loads(line)
                candidates_by_id: dict[str, dict[str, str]] = {}
                duplicate_ids = 0
                for item_quote in item["text_quotes"]:
                    identifier = str(item_quote["quote_id"])
                    if identifier in candidates_by_id:
                        duplicate_ids += 1
                        if candidates_by_id[identifier]["modality"] != "text":
                            raise ValueError(f"Candidate ID has conflicting modalities at {path}:{line_number}")
                        if candidates_by_id[identifier]["text"] != str(item_quote["text"]):
                            candidates_by_id[identifier]["text"] += " " + str(item_quote["text"])
                    else:
                        candidates_by_id[identifier] = {"id": identifier, "modality": "text",
                                                        "text": str(item_quote["text"])}
                for item_quote in item["img_quotes"]:
                    identifier = str(item_quote["quote_id"])
                    if identifier in candidates_by_id:
                        duplicate_ids += 1
                        if candidates_by_id[identifier]["modality"] != "image":
                            raise ValueError(f"Candidate ID has conflicting modalities at {path}:{line_number}")
                        if candidates_by_id[identifier]["text"] != str(item_quote["img_description"]):
                            candidates_by_id[identifier]["text"] += " " + str(item_quote["img_description"])
                    else:
                        candidates_by_id[identifier] = {"id": identifier, "modality": "image",
                                                        "text": str(item_quote["img_description"])}
                candidates = list(candidates_by_id.values())
                gold = {str(identifier) for identifier in item["gold_quotes"]}
                ids = set(candidates_by_id)
                if not gold:
                    unanswerable += 1
                    continue
                if not gold <= ids:
                    raise ValueError(f"Gold ID alignment failed at {path}:{line_number}")
                rows.append({"id": str(item["q_id"]), "question": str(item["question"]),
                             "candidates": candidates, "gold": gold, "duplicate_candidate_ids": duplicate_ids})
    return rows, unanswerable


def load_spiqa(path: Path, split: str) -> list[dict[str, Any]]:
    """Load caption candidates; no raw image pixels or answer text are consumed."""
    source = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for paper_key, paper in source.items():
        if split == "dev":
            candidate_map = paper.get("all_figures", {})
            questions = paper.get("qa", [])
            for index, qa in enumerate(questions):
                gold = {str(qa.get("reference", ""))}
                if not gold or "" in gold or not gold <= {str(key) for key in candidate_map}:
                    continue
                rows.append({"id": f"{paper_key}:{index}", "question": str(qa["question"]),
                             "candidates": [{"id": str(key), "modality": "image", "text": str(value)}
                                            for key, value in candidate_map.items()], "gold": gold})
        else:
            candidate_map = paper.get("all_figures_tables", {})
            questions = paper.get("question", [])
            gold_groups = paper.get("referred_figures_tables", [])
            evidence_groups = paper.get("evidential_info", [])
            passages = paper.get("passages", [])
            if len(questions) != len(gold_groups):
                raise ValueError(f"Question/reference alignment failed for SPIQA paper {paper_key}")
            candidate_ids = {str(key) for key in candidate_map}
            candidates = [{"id": str(key), "modality": "image", "text": str(value)}
                          for key, value in candidate_map.items()]
            for index, (question, gold_values) in enumerate(zip(questions, gold_groups, strict=True)):
                gold = {str(identifier) for identifier in gold_values}
                if not gold or not gold <= candidate_ids:
                    raise ValueError(f"SPIQA gold figure mapping failed for {paper_key}:{index}")
                aligned = True
                contexts: list[str] = []
                if index >= len(evidence_groups):
                    aligned = False
                else:
                    evidence_group = evidence_groups[index]
                    for evidence in evidence_group:
                        context = str(evidence.get("context", "")).strip() if isinstance(evidence, dict) else ""
                        if not context:
                            aligned = False
                            continue
                        normalized_context = normalized_text(context)
                        matches = [passage_index for passage_index, passage in enumerate(passages)
                                   if normalized_context and normalized_context in normalized_text(str(passage))]
                        if not matches:
                            aligned = False
                        else:
                            contexts.append(context)
                            best_match = min(
                                matches,
                                key=lambda passage_index: (
                                    len(normalized_text(str(passages[passage_index]))), passage_index
                                ),
                            )
                            gold.add(f"text:p{best_match}")
                text_candidates = [{"id": f"text:p{passage_index}", "modality": "text", "text": str(passage)}
                                   for passage_index, passage in enumerate(passages)]
                candidates_all = text_candidates + candidates
                aligned = aligned and bool(contexts)
                has_text_gold = any(candidate["id"] in gold for candidate in text_candidates)
                has_image_gold = any(candidate["id"] in gold for candidate in candidates)
                rows.append({"id": f"{paper_key}:{index}", "question": str(question),
                             "candidates": candidates_all, "gold": gold, "alignment_complete": aligned,
                             "cross_modal": has_text_gold and has_image_gold})
    if not rows:
        raise ValueError(f"No aligned SPIQA rows in {path}")
    return rows


def score_bm25(question: str, candidates: list[dict[str, Any]]) -> np.ndarray:
    tokenized = [tokenize(candidate["text"]) for candidate in candidates]
    query = tokenize(question)
    if not query or not any(tokenized):
        return np.zeros(len(candidates), dtype=np.float64)
    values = np.asarray(BM25Okapi(tokenized).get_scores(query), dtype=np.float64)
    return np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)


def modality_indices(candidates: list[dict[str, Any]], modality: str) -> list[int]:
    return [index for index, candidate in enumerate(candidates) if candidate["modality"] == modality]


def stable_rank(indices: list[int], scores: np.ndarray, candidates: list[dict[str, Any]]) -> list[int]:
    return sorted(indices, key=lambda index: (-float(scores[index]), index, candidates[index]["id"] ))


def robust_standardize(scores: np.ndarray, indices: list[int]) -> dict[int, float]:
    values = np.asarray([scores[index] for index in indices], dtype=np.float64)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    scale = 1.4826 * mad
    if scale == 0.0:
        mean = float(np.mean(values))
        std = float(np.std(values))
        scale = std if std > 0.0 else 1.0
        center = mean if std > 0.0 else median
    else:
        center = median
    return {index: (float(scores[index]) - center) / scale for index in indices}


def oracle_selection(candidates: list[dict[str, Any]], scores: np.ndarray, gold: set[str], budget: int) -> list[int]:
    """Use gold modality proportions as a non-deployable allocation upper bound."""
    modalities = ("text", "image")
    available = {modality: modality_indices(candidates, modality) for modality in modalities}
    gold_counts = {modality: sum(candidates[index]["id"] in gold for index in indices)
                   for modality, indices in available.items()}
    total_gold = sum(gold_counts.values())
    if total_gold == 0:
        return []
    quotas = {modality: min(len(available[modality]), int(budget * gold_counts[modality] / total_gold))
              for modality in modalities}
    remaining = min(budget, len(candidates)) - sum(quotas.values())
    modality_priority = sorted(modalities,
                               key=lambda modality: (-(budget * gold_counts[modality] / total_gold
                                                       - int(budget * gold_counts[modality] / total_gold)),
                                                     modality))
    for modality in modality_priority:
        room = len(available[modality]) - quotas[modality]
        added = min(room, remaining)
        quotas[modality] += added
        remaining -= added
    selected = []
    for modality in modalities:
        selected.extend(stable_rank(available[modality], scores, candidates)[:quotas[modality]])
    return selected


def select_indices(policy: str, candidates: list[dict[str, Any]], scores: np.ndarray,
                   gold: set[str], budget: int) -> list[int]:
    all_indices = list(range(len(candidates)))
    text_indices = modality_indices(candidates, "text")
    image_indices = modality_indices(candidates, "image")
    if policy == "global_bm25":
        return stable_rank(all_indices, scores, candidates)[:budget]
    if policy == "calibrated_bm25":
        calibrated: dict[int, float] = {}
        for indices in (text_indices, image_indices):
            if indices:
                calibrated.update(robust_standardize(scores, indices))
        calibrated_scores = np.asarray([calibrated.get(index, 0.0) for index in all_indices])
        return stable_rank(all_indices, calibrated_scores, candidates)[:budget]
    if policy == "balanced_bm25":
        if not text_indices or not image_indices:
            return stable_rank(all_indices, scores, candidates)[:budget]
        text_quota = budget // 2
        image_quota = budget // 2
        if budget % 2:
            if max(scores[text_indices]) >= max(scores[image_indices]):
                text_quota += 1
            else:
                image_quota += 1
        chosen = (stable_rank(text_indices, scores, candidates)[:text_quota]
                  + stable_rank(image_indices, scores, candidates)[:image_quota])
        return stable_rank(chosen, scores, candidates)
    if policy == "text_only":
        return stable_rank(text_indices, scores, candidates)[:budget]
    if policy == "image_only":
        return stable_rank(image_indices, scores, candidates)[:budget]
    if policy == "oracle":
        return oracle_selection(candidates, scores, gold, budget)
    raise ValueError(f"Unknown selection policy {policy}")


def rankings(question: str, candidates: list[dict[str, Any]], gold: set[str]) -> dict[str, list[int]]:
    scores = score_bm25(question, candidates)
    all_indices = list(range(len(candidates)))
    text_indices = modality_indices(candidates, "text")
    image_indices = modality_indices(candidates, "image")
    global_order = stable_rank(all_indices, scores, candidates)
    balanced: list[int] = []
    normalized: list[int] = []
    if text_indices and image_indices:
        equal_slots = len(candidates) // 2
        text_quota = equal_slots + (1 if len(candidates) % 2 and max(scores[text_indices]) >= max(scores[image_indices]) else 0)
        image_quota = len(candidates) - text_quota
        balanced = (stable_rank(text_indices, scores, candidates)[:text_quota]
                    + stable_rank(image_indices, scores, candidates)[:image_quota])
        balanced = sorted(balanced, key=lambda index: (-(scores[index]), index))
        calibrated = {**robust_standardize(scores, text_indices), **robust_standardize(scores, image_indices)}
        normalized = stable_rank(all_indices, np.asarray([calibrated[i] for i in all_indices]), candidates)
    else:
        balanced = global_order.copy()
        normalized = global_order.copy()
    oracle = stable_rank(all_indices, scores, candidates)
    return {
        "global_bm25": global_order,
        "balanced_bm25": balanced,
        "calibrated_bm25": normalized,
        "text_only": stable_rank(text_indices, scores, candidates),
        "image_only": stable_rank(image_indices, scores, candidates),
        "oracle": oracle,
    }


def example_metrics(selected: list[int], candidates: list[dict[str, Any]], gold: set[str]) -> dict[str, float]:
    selected_ids = {candidates[index]["id"] for index in selected}
    hits = len(selected_ids & gold)
    precision = hits / len(selected_ids) if selected_ids else 0.0
    recall = hits / len(gold)
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {"complete": float(gold <= selected_ids), "recall": recall, "f1": f1}


def bootstrap_difference(differences: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    sample_indices = rng.integers(0, len(differences), size=(BOOTSTRAPS, len(differences)))
    means = differences[sample_indices].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def sign_randomization_p(differences: np.ndarray) -> float:
    observed = abs(float(np.mean(differences)))
    rng = np.random.default_rng(SEED + 1)
    extreme = 0
    for _ in range(SIGN_DRAWS):
        signs = rng.choice((-1.0, 1.0), size=len(differences))
        if abs(float(np.mean(differences * signs))) >= observed:
            extreme += 1
    return (extreme + 1) / (SIGN_DRAWS + 1)


def contrast_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"n": 0, "status": "no aligned cross-modal examples"}
    differences = np.asarray([
        record["metrics"]["calibrated_bm25"]["10"]["complete"]
        - record["metrics"]["global_bm25"]["10"]["complete"] for record in records
    ], dtype=np.float64)
    ci = bootstrap_difference(differences)
    return {"contrast": "calibrated_bm25 - global_bm25", "budget": 10, "n": len(differences),
            "mean_complete_coverage_difference": float(differences.mean()),
            "bootstrap_95_ci": [ci[0], ci[1]], "paired_sign_randomization_p": sign_randomization_p(differences),
            "seed": SEED, "bootstrap_resamples": BOOTSTRAPS, "sign_draws": SIGN_DRAWS}


def gap_summary(records: list[dict[str, Any]], policy: str = "global_bm25", budget: int = 10) -> dict[str, Any]:
    if not records:
        return {"n": 0, "status": "no aligned examples"}
    gaps = np.asarray([record["metrics"][policy][str(budget)]["recall"]
                       - record["metrics"][policy][str(budget)]["complete"] for record in records], dtype=np.float64)
    ci = bootstrap_difference(gaps)
    return {"policy": policy, "budget": budget, "n": len(gaps), "mean_example_recall_minus_complete_coverage": float(gaps.mean()),
            "bootstrap_95_ci": [ci[0], ci[1]], "paired_sign_randomization_p_vs_zero": sign_randomization_p(gaps),
            "seed": SEED, "bootstrap_resamples": BOOTSTRAPS, "sign_draws": SIGN_DRAWS}


def subgroup_gap_difference(cross_modal: list[dict[str, Any]], single_modal: list[dict[str, Any]]) -> dict[str, Any]:
    if not cross_modal or not single_modal:
        return {"status": "one or both strata are empty", "n_cross_modal": len(cross_modal),
                "n_single_modal": len(single_modal)}
    cross = np.asarray([record["metrics"]["global_bm25"]["10"]["recall"]
                        - record["metrics"]["global_bm25"]["10"]["complete"]
                        for record in cross_modal], dtype=np.float64)
    single = np.asarray([record["metrics"]["global_bm25"]["10"]["recall"]
                         - record["metrics"]["global_bm25"]["10"]["complete"]
                         for record in single_modal], dtype=np.float64)
    observed = float(cross.mean() - single.mean())
    rng = np.random.default_rng(SEED + 2)
    cross_indices = rng.integers(0, len(cross), size=(BOOTSTRAPS, len(cross)))
    single_indices = rng.integers(0, len(single), size=(BOOTSTRAPS, len(single)))
    boot = cross[cross_indices].mean(axis=1) - single[single_indices].mean(axis=1)
    combined = np.concatenate((cross, single))
    n_cross = len(cross)
    extreme = 0
    for _ in range(SIGN_DRAWS):
        shuffled = rng.permutation(combined)
        if abs(float(shuffled[:n_cross].mean() - shuffled[n_cross:].mean())) >= abs(observed):
            extreme += 1
    return {"contrast": "cross_modal_gap - single_modal_gap", "budget": 10,
            "n_cross_modal": len(cross), "n_single_modal": len(single),
            "mean_difference": observed,
            "bootstrap_95_ci": [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))],
            "permutation_p": (extreme + 1) / (SIGN_DRAWS + 1), "seed": SEED,
            "bootstrap_resamples": BOOTSTRAPS, "permutation_draws": SIGN_DRAWS}


def holm_adjust(values: list[float]) -> list[float]:
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=np.float64)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * values[index]))
        adjusted[index] = running
    return adjusted.tolist()


def policy_contrasts(records: list[dict[str, Any]], group: str) -> list[dict[str, Any]]:
    contrasts = []
    for policy in POLICIES:
        if policy == "global_bm25":
            continue
        diff = np.asarray([record["metrics"][policy]["10"]["complete"]
                           - record["metrics"]["global_bm25"]["10"]["complete"]
                           for record in records], dtype=np.float64)
        if len(diff) == 0:
            continue
        ci = bootstrap_difference(diff)
        contrasts.append({"group": group, "policy": policy, "n": len(diff),
                          "mean_complete_coverage_difference": float(diff.mean()),
                          "bootstrap_95_ci": [ci[0], ci[1]],
                          "paired_sign_randomization_p": sign_randomization_p(diff)})
    adjusted = holm_adjust([row["paired_sign_randomization_p"] for row in contrasts])
    for row, p_adjusted in zip(contrasts, adjusted, strict=True):
        row["holm_adjusted_p"] = p_adjusted
    return contrasts


def summarize(records: list[dict[str, Any]], budgets: tuple[int, ...]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    detail: dict[str, Any] = {}
    for budget in budgets:
        detail[str(budget)] = {}
        for policy in POLICIES:
            values = [record["metrics"][policy][str(budget)] for record in records]
            n = len(values)
            row = {"budget": budget, "policy": policy, "n": n,
                   "complete_evidence_coverage": float(np.mean([value["complete"] for value in values])),
                   "micro_evidence_recall": float(sum(value["hits"] for value in values) / sum(value["gold_count"] for value in values)),
                   "mean_example_f1": float(np.mean([value["f1"] for value in values]))}
            metrics.append(row)
            detail[str(budget)][policy] = row
    cross_modal_rows = [record for record in records if record["cross_modal"]]
    single_modal_rows = [record for record in records if not record["cross_modal"]]
    gap_curves: dict[str, Any] = {}
    for group, subset in (("all", records), ("cross_modal", cross_modal_rows),
                          ("single_modal", single_modal_rows)):
        gap_curves[group] = {}
        for budget in budgets:
            gap_curves[group][str(budget)] = {
                policy: {"n": len(subset),
                         "mean_example_recall_minus_complete_coverage": float(np.mean([
                             record["metrics"][policy][str(budget)]["recall"]
                             - record["metrics"][policy][str(budget)]["complete"]
                             for record in subset])) if subset else None}
                for policy in POLICIES
            }
    return metrics, {"by_budget": detail,
                     "evidence_sufficiency_gap_curves": gap_curves,
                     "overall_comparison": contrast_summary(records),
                     "cross_modal_comparison": contrast_summary(cross_modal_rows),
                     "primary_evidence_sufficiency_gap": gap_summary(cross_modal_rows),
                     "overall_evidence_sufficiency_gap": gap_summary(records),
                     "cross_modal_vs_single_modal_gap": subgroup_gap_difference(cross_modal_rows,
                                                                                 single_modal_rows),
                     "exploratory_policy_comparisons": policy_contrasts(cross_modal_rows, "cross_modal")}


def run(dataset: str, split: str, allow_heldout: bool = False) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dataset_info = manifest["datasets"][dataset]
    split_key = "development" if split == "dev" else "test"
    data_record = dataset_info[split_key]
    data_path = ROOT / data_record["file"]
    verify_dataset_file(data_path, data_record)
    if split == "test":
        if not allow_heldout:
            raise PermissionError("Held-out run requires --allow-heldout after protocol/evaluator freeze")
        if git_value("status", "--porcelain"):
            raise RuntimeError("Held-out evaluation requires a clean committed worktree")
        expected = manifest.get("evaluator_sha256")
        expected_protocol = manifest.get("protocol_sha256")
        if not expected or sha256(Path(__file__)) != expected or sha256(PROTOCOL) != expected_protocol:
            raise RuntimeError("Held-out evaluator/protocol does not match frozen manifest")
    started = time.perf_counter()
    unanswerable_count = 0
    excluded: list[str] = []
    if dataset == "mmdocrag":
        rows, unanswerable_count = load_mmdoc(data_path)
    else:
        all_rows = load_spiqa(data_path, split)
        if split == "test":
            excluded = [row["id"] for row in all_rows if not row.get("alignment_complete", True)]
            rows = [row for row in all_rows if row.get("alignment_complete", True)]
        else:
            rows = all_rows
    raw_records: list[dict[str, Any]] = []
    for row in rows:
        scores = score_bm25(row["question"], row["candidates"])
        orders = rankings(row["question"], row["candidates"], row["gold"])
        record_metrics: dict[str, dict[str, Any]] = {}
        record_selected: dict[str, dict[str, list[str]]] = {}
        for policy, order in orders.items():
            record_metrics[policy] = {}
            record_selected[policy] = {}
            for budget in BUDGETS:
                selected = select_indices(policy, row["candidates"], scores, row["gold"],
                                          min(budget, len(row["candidates"])))
                record_selected[policy][str(budget)] = [row["candidates"][index]["id"] for index in selected]
                measured = example_metrics(selected, row["candidates"], row["gold"])
                measured["hits"] = len({row["candidates"][index]["id"] for index in selected} & row["gold"])
                measured["gold_count"] = len(row["gold"])
                record_metrics[policy][str(budget)] = measured
        gold_modalities = {candidate["modality"] for candidate in row["candidates"]
                           if candidate["id"] in row["gold"]}
        cross_modal = ("cross_modal" in row and row["cross_modal"] if dataset == "spiqa"
                       else gold_modalities.issuperset({"text", "image"}))
        raw_records.append({"id": row["id"], "gold_ids": sorted(row["gold"]),
                            "cross_modal": cross_modal,
                            "duplicate_candidate_ids": row.get("duplicate_candidate_ids", 0),
                            "rankings": {policy: [row["candidates"][i]["id"] for i in order]
                                         for policy, order in orders.items()},
                            "selected_by_budget": record_selected,
                            "metrics": record_metrics})
    metrics, inference = summarize(raw_records, BUDGETS)
    config = {"dataset": dataset, "split": split, "budgets": BUDGETS, "policies": POLICIES,
              "score": "BM25Okapi per-question candidate pool", "seed": SEED,
              "bootstrap_resamples": BOOTSTRAPS, "sign_draws": SIGN_DRAWS}
    config_hash = canonical_hash(config)[:12]
    try:
        commit = git_value("rev-parse", "HEAD")
    except subprocess.CalledProcessError:
        commit = "UNCOMMITTED"
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{dataset}_{split}_{config_hash}"
    out = ROOT / "results" / run_name
    out.mkdir(parents=True, exist_ok=False)
    raw = {"schema_version": 1, "dataset": dataset, "split": split, "dataset_sha256": data_record["sha256"],
           "config": config, "config_hash": config_hash, "git_commit": commit,
           "evaluator_sha256": sha256(Path(__file__)), "protocol_sha256": sha256(PROTOCOL),
           "platform": platform.platform(), "processor": platform.processor(),
           "logical_cpu_count": os.cpu_count(), "python": sys.version,
           "elapsed_seconds": time.perf_counter() - started,
           "n": len(raw_records), "unanswerable_count": unanswerable_count,
           "duplicate_candidate_id_occurrences": sum(record["duplicate_candidate_ids"]
                                                       for record in raw_records),
           "excluded_unaligned_count": len(excluded), "excluded_unaligned_ids": excluded,
           "records": raw_records, "inference": inference}
    (out / "raw.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    with (out / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    summary = {"run": run_name, "config_hash": config_hash, "n": len(raw_records),
               "unanswerable_count": unanswerable_count, "excluded_unaligned_count": len(excluded),
               "overall_comparison": inference["overall_comparison"],
               "cross_modal_comparison": inference["cross_modal_comparison"],
               "primary_evidence_sufficiency_gap": inference["primary_evidence_sufficiency_gap"],
               "cross_modal_vs_single_modal_gap": inference["cross_modal_vs_single_modal_gap"]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("mmdocrag", "spiqa"), required=True)
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--allow-heldout", action="store_true")
    args = parser.parse_args()
    result = run(args.dataset, args.split, args.allow_heldout)
    print(result)


if __name__ == "__main__":
    main()
