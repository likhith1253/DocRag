"""
eval.benchmark.artifacts.error_analysis
==========================================
Failure analysis: categorize and store per-query failures for qualitative analysis.

Generates:
  error_analysis/failures.jsonl        : one record per failure (answer empty, retrieval miss)
  error_analysis/failure_categories.json : breakdown by category, difficulty, system

Research mapping:
  All RQs — error analysis reveals WHY metrics differ between systems.
  This is qualitative evidence supporting quantitative results.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Failure detection
# ---------------------------------------------------------------------------

def _is_retrieval_failure(
    retrieved_files: List[str],
    relevant_files: List[str],
    k: int = 5,
) -> bool:
    """Returns True if no relevant file was found in top-K retrieved files."""
    if not relevant_files:
        return False
    relevant_norm = {p.replace("\\", "/").strip().lower() for p in relevant_files}
    retrieved_norm = {p.replace("\\", "/").strip().lower() for p in retrieved_files[:k]}
    return not bool(relevant_norm & retrieved_norm)


def _is_generation_failure(
    answer: str,
    expected: str,
    token_f1_threshold: float = 0.3,
) -> bool:
    """Returns True if Token F1 is below threshold or answer is empty."""
    if not answer or not answer.strip():
        return True
    # Simple token overlap check
    from eval.benchmark.metrics.generation import token_f1
    f1 = token_f1(answer, expected)
    return f1 < token_f1_threshold


# ---------------------------------------------------------------------------
# Error analysis generation
# ---------------------------------------------------------------------------

def generate_error_analysis(
    raw_records: Dict[str, List[Dict[str, Any]]],
    output_dir: str,
    retrieval_k: int = 5,
    generation_f1_threshold: float = 0.3,
) -> Dict[str, Any]:
    """
    Analyze failures per system and generate error analysis artifacts.

    Parameters
    ----------
    raw_records : dict[system_name, list[dict]]
        Raw per-query records loaded from JSONL files.
    output_dir : str
        Experiment output root directory.
    retrieval_k : int
        K threshold for retrieval failure detection.
    generation_f1_threshold : float
        Token F1 threshold below which a generation is considered a failure.

    Returns
    -------
    dict — summary of failure counts per system.
    """
    error_dir = os.path.join(output_dir, "error_analysis")
    os.makedirs(error_dir, exist_ok=True)

    all_failures = []
    summary: Dict[str, Any] = {}

    for sys_name, records in raw_records.items():
        sys_failures = []
        retrieval_fails = 0
        generation_fails = 0
        both_fails = 0
        category_breakdown: Dict[str, int] = defaultdict(int)
        difficulty_breakdown: Dict[str, int] = defaultdict(int)

        for record in records:
            retrieved_files = [c.get("file_path", "") for c in record.get("retrieved_chunks", [])]
            relevant_files = record.get("relevant_sources", [])
            answer = record.get("answer", "")
            expected = record.get("expected_answer", "")
            category = record.get("category", "unknown")
            difficulty = record.get("difficulty", "unknown")
            question_id = record.get("question_id", "")

            ret_fail = _is_retrieval_failure(retrieved_files, relevant_files, k=retrieval_k)
            gen_fail = _is_generation_failure(answer, expected, generation_f1_threshold) if expected else False

            if ret_fail or gen_fail:
                failure_type = []
                if ret_fail and gen_fail:
                    failure_type = ["retrieval", "generation"]
                    both_fails += 1
                elif ret_fail:
                    failure_type = ["retrieval"]
                    retrieval_fails += 1
                else:
                    failure_type = ["generation"]
                    generation_fails += 1

                category_breakdown[category] += 1
                difficulty_breakdown[difficulty] += 1

                failure_record = {
                    "system": sys_name,
                    "question_id": question_id,
                    "question": record.get("question", ""),
                    "expected_answer": expected,
                    "actual_answer": answer,
                    "category": category,
                    "difficulty": difficulty,
                    "failure_types": failure_type,
                    "retrieved_files": retrieved_files[:retrieval_k],
                    "relevant_files": relevant_files,
                    "error_message": record.get("error", None),
                }
                sys_failures.append(failure_record)
                all_failures.append(failure_record)

        summary[sys_name] = {
            "total_queries": len(records),
            "total_failures": len(sys_failures),
            "failure_rate": round(len(sys_failures) / len(records), 4) if records else 0,
            "retrieval_failures": retrieval_fails,
            "generation_failures": generation_fails,
            "both_failures": both_fails,
            "by_category": dict(category_breakdown),
            "by_difficulty": dict(difficulty_breakdown),
        }

    # Write all_failures.jsonl
    failures_path = os.path.join(error_dir, "failures.jsonl")
    with open(failures_path, "w", encoding="utf-8") as f:
        for failure in all_failures:
            f.write(json.dumps(failure, ensure_ascii=False) + "\n")

    # Write failure_categories.json
    categories_path = os.path.join(error_dir, "failure_categories.json")
    with open(categories_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary
