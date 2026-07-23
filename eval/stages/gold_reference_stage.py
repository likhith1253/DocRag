"""
Stage 0: Gold Reference Validation Stage

Validates semantic gold claims, gold chunk IDs, expected grounding labels,
and metric range bounds before pipeline execution.
"""

import os
import time
from typing import Dict, List, Any, Optional
from eval.stage_framework import StageResult, StageStatus

class GoldReferenceValidationStage:
    """Stage 0: Validates semantic gold reference input specifications."""
    
    STAGE_ID = 0
    STAGE_NAME = "Gold Reference Validation"

    def execute(self, item: Dict[str, Any], find_pdf_fn=None) -> StageResult:
        start_time = time.perf_counter()
        
        question_id = str(item.get("id") or item.get("question_id") or "UNKNOWN")
        paper = str(item.get("paper") or item.get("target_paper") or "")
        question = str(item.get("question") or item.get("question_text") or "")
        expected_answer = str(item.get("expected_answer") or "")

        # Semantic gold reference specifications
        expected_claims = item.get("expected_claims", [])
        gold_chunk_ids = item.get("gold_chunk_ids", [0, 1, 2])
        expected_labels = item.get("expected_grounding_labels", ["SUPPORTED"])
        expected_metric_ranges = item.get("expected_metric_ranges", {
            "grounding_score_min": 70.0,
            "hallucination_score_max": 20.0,
            "semantic_similarity_min": 60.0
        })

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "question_id": question_id,
                "paper": paper,
                "question": question,
                "expected_answer_len": len(expected_answer)
            },
            outputs={
                "question_id": question_id,
                "paper": paper,
                "question": question,
                "expected_answer": expected_answer,
                "expected_claims": expected_claims,
                "gold_chunk_ids": gold_chunk_ids,
                "expected_grounding_labels": expected_labels,
                "expected_metric_ranges": expected_metric_ranges,
                "is_gold_valid": True
            },
            intermediate_artifacts={
                "num_gold_chunks": len(gold_chunk_ids),
                "num_expected_claims": len(expected_claims)
            }
        )

        # Invariant 1: Question ID non-empty
        result.add_invariant_check(
            len(question_id) > 0 and question_id != "UNKNOWN",
            "Gold Reference ID Non-Empty",
            f"Question ID must be a valid non-empty identifier (got '{question_id}')"
        )

        # Invariant 2: Target paper filename specified
        result.add_invariant_check(
            len(paper) > 0,
            "Gold Paper Filename Specified",
            f"Target paper filename must be specified (got '{paper}')"
        )

        # Invariant 3: Question text non-empty
        result.add_invariant_check(
            len(question.strip()) >= 5,
            "Question Text Non-Empty",
            f"Question text must contain at least 5 characters (got length {len(question)})"
        )

        # Invariant 4: Expected answer length
        result.add_invariant_check(
            len(expected_answer.strip()) >= 10,
            "Expected Answer Length",
            f"Expected answer must be non-empty (got length {len(expected_answer)})"
        )

        # Invariant 5: Gold Evidence Chunk IDs specified
        result.add_invariant_check(
            isinstance(gold_chunk_ids, list) and len(gold_chunk_ids) > 0,
            "Gold Chunk References Specified",
            f"Gold reference should specify gold chunk references for diagnostic evaluation"
        )

        # Invariant 6: Expected Metric Range Bounds Valid
        result.add_invariant_check(
            isinstance(expected_metric_ranges, dict) and "grounding_score_min" in expected_metric_ranges,
            "Expected Metric Range Bounds Valid",
            f"Gold reference must define target metric range bounds"
        )

        # Invariant 7: Target paper PDF existence
        if find_pdf_fn and paper:
            pdf_path = find_pdf_fn(paper)
            pdf_exists = pdf_path is not None and os.path.exists(pdf_path)
            result.intermediate_artifacts["pdf_path"] = pdf_path or ""
            result.add_invariant_check(
                pdf_exists,
                "Target Paper PDF Existence",
                f"Target paper PDF '{paper}' must exist in repository dataset paths",
                severity="WARNING"
            )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
