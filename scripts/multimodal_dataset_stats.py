"""Validate frozen benchmark files and create source-derived statistics."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from eval.multimodal_selection import ROOT, sha256

MANIFEST = ROOT / "data/frozen/multimodal_manifest.json"


def dataset_file(record: dict[str, object]) -> Path:
    path = ROOT / str(record["file"])
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise ValueError(f"Frozen dataset file missing or corrupt: {path}")
    return path


def mmdoc_stats(record: dict[str, object]) -> dict[str, object]:
    path = dataset_file(record)
    n = duplicate_candidate_ids = 0
    documents: set[str] = set()
    gold_total = text_total = image_total = 0
    cross_modal = Counter()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            n += 1
            documents.add(str(row.get("doc_name", "")))
            gold_total += len(row.get("gold_quotes", []))
            text_total += len(row.get("text_quotes", []))
            image_total += len(row.get("img_quotes", []))
            quotes = row.get("text_quotes", []) + row.get("img_quotes", [])
            duplicate_candidate_ids += len(quotes) - len({quote["quote_id"] for quote in quotes})
            labels = {str(value).casefold() for value in row.get("evidence_modality_type", [])}
            contains_text = any("text" in label for label in labels)
            contains_visual = any(any(kind in label for kind in ("image", "figure", "table", "chart"))
                                  for label in labels)
            cross_modal["text_and_visual"] += int(contains_text and contains_visual)
            cross_modal["text_only"] += int(contains_text and not contains_visual)
            cross_modal["visual_only"] += int(contains_visual and not contains_text)
    return {"questions": n, "unique_documents": len(documents),
            "duplicate_candidate_id_occurrences": duplicate_candidate_ids,
            "mean_candidates_text": text_total / n if n else 0.0,
            "mean_candidates_image": image_total / n if n else 0.0,
            "mean_gold_quotes": gold_total / n if n else 0.0,
            "evidence_modality_counts": dict(cross_modal)}


def spiqa_stats(record: dict[str, object], split: str) -> dict[str, object]:
    path = dataset_file(record)
    data = json.loads(path.read_text(encoding="utf-8"))
    n = gold_total = candidate_total = 0
    type_counts: Counter[str] = Counter()
    for paper in data.values():
        if split == "dev":
            questions = paper.get("qa", [])
            candidates = paper.get("all_figures", {})
            for question in questions:
                n += 1
                candidate_total += len(candidates)
                gold_total += int(bool(question.get("reference")))
        else:
            questions = paper.get("question", [])
            references = paper.get("referred_figures_tables", [])
            if len(questions) != len(references):
                raise ValueError("SPIQA question/reference count mismatch")
            candidates = paper.get("all_figures_tables", {})
            types = paper.get("question_type", [])
            for index, (question, gold) in enumerate(zip(questions, references, strict=True)):
                n += 1
                candidate_total += len(candidates)
                gold_total += len(gold)
                if index < len(types):
                    type_counts[str(types[index])] += 1
    return {"papers": len(data), "questions": n,
            "mean_visual_candidates_per_question": candidate_total / n if n else 0.0,
            "mean_gold_visual_references": gold_total / n if n else 0.0,
            "question_types": dict(sorted(type_counts.items()))}


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = {"schema_version": 1,
              "mmdocrag": {split: mmdoc_stats(data[split]) for split in ("development", "test")
                           for data in (manifest["datasets"]["mmdocrag"],)},
              "spiqa": {"development": spiqa_stats(manifest["datasets"]["spiqa"]["development"], "dev"),
                        "test": spiqa_stats(manifest["datasets"]["spiqa"]["test"], "test")}}
    config_hash = hashlib.sha256(json.dumps(result, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    output = ROOT / "results" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_multimodal_dataset_stats_{config_hash}"
    output.mkdir(parents=True, exist_ok=False)
    result["config_hash"] = config_hash
    result["generated_utc"] = datetime.now(timezone.utc).isoformat()
    result["manifest_sha256"] = sha256(MANIFEST)
    result["script_sha256"] = sha256(Path(__file__))
    result["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                          capture_output=True, text=True).stdout.strip()
    result["python"] = sys.version
    result["platform"] = platform.platform()
    (output / "dataset_stats.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
