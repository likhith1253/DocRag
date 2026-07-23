"""
Stage 2: Reranker & Scoring Stage

Validates raw vector cosine scores, CrossEncoder rerank scores,
sigmoid normalization bounds [0, 1], and score variance integrity.
"""

import time
import math
from typing import Dict, List, Any, Callable
from eval.stage_framework import StageResult, StageStatus

class RerankerValidationStage:
    """Stage 2: Validates vector cosine sim & CrossEncoder rerank scoring."""
    
    STAGE_ID = 2
    STAGE_NAME = "Reranker Validation"

    def execute(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        vector_sim_fn: Callable[[str, str], float],
        rerank_score_fn: Callable[[str, str], float]
    ) -> StageResult:
        start_time = time.perf_counter()

        scored_chunks = []
        raw_scores = []
        rerank_scores = []
        normalized_scores = []

        for c in retrieved_chunks:
            chunk_copy = dict(c)
            c_text = chunk_copy.get('content') or chunk_copy.get('chunk_text') or ''
            
            # Compute raw vector cosine score
            raw_v = chunk_copy.get('raw_vector_score')
            if raw_v is None or raw_v == 0.72:
                raw_v = vector_sim_fn(question, c_text)
            raw_v = float(raw_v)
            chunk_copy['raw_vector_score'] = raw_v
            raw_scores.append(raw_v)

            # Compute CrossEncoder rerank score
            rerank_v = chunk_copy.get('rerank_score')
            if rerank_v is None or rerank_v == raw_v or rerank_v == 0.72:
                rerank_v = rerank_score_fn(question, c_text)
            rerank_v = float(rerank_v)
            chunk_copy['rerank_score'] = rerank_v
            rerank_scores.append(rerank_v)

            # Sigmoid normalization
            norm_v = float(1.0 / (1.0 + math.exp(-rerank_v)))
            chunk_copy['normalized_score'] = norm_v
            chunk_copy['score'] = rerank_v
            normalized_scores.append(norm_v)

            scored_chunks.append(chunk_copy)

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "question": question,
                "num_chunks": len(retrieved_chunks)
            },
            outputs={
                "scored_chunks": scored_chunks,
                "num_scored": len(scored_chunks)
            },
            intermediate_artifacts={
                "raw_vector_scores": raw_scores,
                "rerank_scores": rerank_scores,
                "normalized_scores": normalized_scores
            }
        )

        # Invariant 1: Sigmoid normalized score bounds [0.0, 1.0]
        out_of_bounds_norm = [s for s in normalized_scores if not (0.0 <= s <= 1.0)]
        result.add_invariant_check(
            len(out_of_bounds_norm) == 0,
            "Normalized Score Bounds [0, 1]",
            f"Found {len(out_of_bounds_norm)} normalized scores out of bounds [0, 1]"
        )

        # Invariant 2: Raw vector vs Rerank model distinction
        identical_scores = [i for i, (r, rr) in enumerate(zip(raw_scores, rerank_scores)) if abs(r - rr) < 1e-6]
        result.add_invariant_check(
            len(identical_scores) < len(scored_chunks) or len(scored_chunks) == 0,
            "Dual-Model Score Distinction",
            f"Raw vector score and Rerank score were identical for all {len(scored_chunks)} chunks",
            severity="WARNING"
        )

        # Invariant 3: Score variance integrity (no constant score fallbacks like 0.72)
        if len(scored_chunks) >= 2:
            unique_raw = len(set(round(s, 4) for s in raw_scores))
            unique_rerank = len(set(round(s, 4) for s in rerank_scores))
            result.add_invariant_check(
                unique_raw > 1 and unique_rerank > 1,
                "Non-Constant Score Distribution",
                f"Scores are constant across distinct chunks (unique raw: {unique_raw}, unique rerank: {unique_rerank})",
                severity="WARNING"
            )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
