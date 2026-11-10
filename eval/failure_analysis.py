"""Create a deterministic retrieval-only failure report from a raw study run."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def analyze(raw_path: Path) -> dict[str, Any]:
    raw_bytes = raw_path.read_bytes()
    raw = json.loads(raw_bytes)
    systems = raw["config"]["systems"]
    records = raw["per_question"]
    repo_root = Path(__file__).resolve().parents[1]
    report: dict[str, Any] = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip(),
        "git_worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True).strip()),
        "analyzer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "source_config_sha256": raw["config_sha256"],
        "source_dataset_sha256": raw["dataset_sha256"],
        "taxonomy_scope": "retrieval-only; parser loss, generation errors, verifier misses, false refusals, and infrastructure failures are not observed by this experiment",
        "counts": {},
    }
    for system in systems:
        counts = {
            "unanswerable": 0,
            "answerable_but_evidence_unmappable": 0,
            "mappable_answerable": 0,
            "retrieval_miss_at_10": 0,
            "partial_evidence_retrieval_at_10": 0,
            "all_mapped_evidence_retrieved_at_10": 0,
            "table_figure_reference_questions": 0,
            "table_figure_reference_miss_at_10": 0,
        }
        examples = []
        for record in records:
            if not record.get("answerable", False):
                counts["unanswerable"] += 1
                continue
            if not record.get("mappable", False):
                counts["answerable_but_evidence_unmappable"] += 1
                continue
            counts["mappable_answerable"] += 1
            relevant = set(record["gold_passage_ids"])
            retrieved = record.get("rankings", {}).get(system, [])[:10]
            hit_count = len(relevant & set(retrieved))
            if hit_count == 0:
                counts["retrieval_miss_at_10"] += 1
                examples.append({
                    "system": system,
                    "question_id": record["question_id"],
                    "paper_id": record["paper_id"],
                    "question": record["question"],
                    "gold_evidence_text": record.get("gold_evidence_text", []),
                    "gold_passage_ids": sorted(relevant),
                    "retrieved_passage_ids": retrieved,
                    "retrieved_types": record.get("ranking_types", {}).get(system, [])[:10],
                })
            elif hit_count < len(relevant):
                counts["partial_evidence_retrieval_at_10"] += 1
            else:
                counts["all_mapped_evidence_retrieved_at_10"] += 1
            is_structural = bool({"table_reference", "figure_reference"} & set(record.get("gold_types", [])))
            if is_structural:
                counts["table_figure_reference_questions"] += 1
                if hit_count == 0:
                    counts["table_figure_reference_miss_at_10"] += 1
        report["counts"][system] = counts
        report.setdefault("representative_retrieval_misses", {})[system] = examples[:5]
    return report


def _tex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def write_tex(report: dict[str, Any], output: Path) -> None:
    lines = [
        "% Generated from failure_analysis.json; do not edit by hand.",
        r"\begin{tabular}{lrrrr}", r"\toprule",
        "System & Miss@10 & Partial & All evidence & Table/figure miss " + chr(92) * 2,
        r"\midrule",
    ]
    for system, counts in report["counts"].items():
        lines.append(
            f"{_tex_escape(system)} & {counts['retrieval_miss_at_10']} & "
            f"{counts['partial_evidence_retrieval_at_10']} & "
            f"{counts['all_mapped_evidence_retrieved_at_10']} & "
            f"{counts['table_figure_reference_miss_at_10']}/{counts['table_figure_reference_questions']} "
            + chr(92) * 2
        )
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_examples(report: dict[str, Any], output: Path) -> None:
    lines = [r"\paragraph{Representative structure-aware misses.}"]
    examples = report.get("representative_retrieval_misses", {}).get("structure", [])[:3]
    if examples:
        lines.append(r"\begin{itemize}")
        for example in examples:
            question = _tex_escape(example["question"])
            qid = _tex_escape(example["question_id"])
            gold = "; ".join(_tex_escape(text) for text in example.get("gold_evidence_text", []))
            gold = gold[:500]
            lines.append(
                f"\\item Structure-aware retrieval miss ({qid}): {question} "
                f"Gold annotated evidence: \\emph{{{gold}}}."
            )
        lines.append(r"\end{itemize}")
    else:
        lines.append("No structure-aware retrieval misses were recorded at the registered cutoff.")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_json", type=Path)
    args = parser.parse_args()
    raw_path = args.raw_json.resolve()
    report = analyze(raw_path)
    output = raw_path.parent / "failure_analysis.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_tex(report, raw_path.parent / "failure_analysis.tex")
    write_examples(report, raw_path.parent / "failure_examples.tex")
    print(output)


if __name__ == "__main__":
    main()
