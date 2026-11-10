"""Aggregate split statistics without exporting test questions or answers."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from eval.qasper_study import _passages, _questions, normalize, verify_data

ROOT = Path(__file__).resolve().parents[1]


def summarize(split: str) -> dict[str, Any]:
    dataset_path, manifest = verify_data(split)
    frame = pd.read_parquet(dataset_path)
    stats: dict[str, Any] = {
        "papers": len(frame), "questions": 0, "answerable": 0, "unanswerable": 0,
        "answerable_with_evidence": 0, "mappable_answerable": 0,
        "unmappable_answerable": 0, "passages": 0,
        "passages_by_kind": {"paragraph": 0, "table": 0, "figure": 0, "caption": 0},
    }
    for _, row in frame.iterrows():
        passages = _passages(row)
        stats["passages"] += len(passages)
        for passage in passages:
            stats["passages_by_kind"][passage.kind] = stats["passages_by_kind"].get(passage.kind, 0) + 1
        for question in _questions(row):
            stats["questions"] += 1
            if question.unanswerable:
                stats["unanswerable"] += 1
                continue
            stats["answerable"] += 1
            gold = [normalize(text) for text in question.gold_evidence if normalize(text)]
            if gold:
                stats["answerable_with_evidence"] += 1
            mapped = any(any(evidence in normalize(passage.text) for evidence in gold) for passage in passages)
            if mapped:
                stats["mappable_answerable"] += 1
            else:
                stats["unmappable_answerable"] += 1
    return {
        "source_sha256": manifest["files"][split]["sha256"],
        "source_bytes": manifest["files"][split]["bytes"],
        **stats,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", default="train,validation")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "dataset_stats")
    args = parser.parse_args()
    splits = [split.strip() for split in args.splits.split(",") if split.strip()]
    unknown = set(splits) - {"train", "validation", "test"}
    if unknown:
        parser.error(f"unknown split(s): {', '.join(sorted(unknown))}")
    manifest = json.loads((ROOT / "data/frozen/qasper_manifest.json").read_text(encoding="utf-8"))
    git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "git_worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip()),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "dataset": manifest["dataset"],
        "dataset_revision": manifest["revision"],
        "statistics_method": "counts only; no question text, answers, or system rankings are exported",
        "splits": {split: summarize(split) for split in splits},
    }
    config = {"splits": splits, "dataset_revision": manifest["revision"],
              "source_hashes": {split: manifest["files"][split]["sha256"] for split in splits}}
    payload["config_sha256"] = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_qasper_stats.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
