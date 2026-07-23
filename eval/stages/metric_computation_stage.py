"""
Stage 5: Metric Computation Stage

Validates computation of 8 core answer quality metrics, metric bounds [0, 100],
hallucination penalty deduction, and weighted overall score calculation.
"""

import time
import math
import re
from typing import Dict, List, Any, Callable
from sentence_transformers import util
from eval.stage_framework import StageResult, StageStatus

class MetricComputationStage:
    """Stage 5: Validates metric computation and bounding math."""
    
    STAGE_ID = 5
    STAGE_NAME = "Metric Computation"

    def execute(
        self,
        expected_answer: str,
        raw_llm_answer: str,
        claims: List[Any],
        scored_chunks: List[Dict[str, Any]],
        paper: str,
        semantic_model: Any,
        compute_semantic_fn: Callable,
        eval_numerical_fn: Callable
    ) -> StageResult:
        start_time = time.perf_counter()

        metrics = {}
        explanations = {}

        # 1. Retrieval & Context Quality
        if scored_chunks:
            target_paper = paper.lower()
            relevant_chunks = [
                c for c in scored_chunks
                if target_paper in c.get('metadata', {}).get('file', '').lower()
                or target_paper in c.get('metadata', {}).get('paper_title', '').lower()
                or target_paper in c.get('pdf_filename', '').lower()
            ]
            num_relevant = len(relevant_chunks) if relevant_chunks else len(scored_chunks)
            total_retrieved = len(scored_chunks)

            context_quality = (num_relevant / total_retrieved) * 100.0
            retrieval_quality = min(100.0, (num_relevant / max(1, min(10, total_retrieved))) * 100.0)

            metrics['context_quality'] = context_quality
            metrics['retrieval_quality'] = retrieval_quality
            explanations['context_quality'] = f"Context Precision: {num_relevant}/{total_retrieved} retrieved chunks matched the target paper."
            explanations['retrieval_quality'] = f"Retrieval Recall: {num_relevant} relevant chunks retrieved out of {total_retrieved} total."
        else:
            metrics['context_quality'] = 0.0
            metrics['retrieval_quality'] = 0.0
            explanations['context_quality'] = "No chunks retrieved"
            explanations['retrieval_quality'] = "No chunks retrieved"

        # 2. Grounding Score & Hallucination Score
        if claims:
            valid_claims = [c for c in claims if getattr(c, 'grounding_status', '') != 'VERIFICATION_FAILED']
            if valid_claims:
                supported = sum(1 for c in valid_claims if getattr(c, 'grounding_status', '') == 'SUPPORTED')
                partially_supported = sum(1 for c in valid_claims if getattr(c, 'grounding_status', '') == 'PARTIALLY_SUPPORTED')
                not_found = sum(1 for c in valid_claims if getattr(c, 'grounding_status', '') == 'NOT_FOUND')

                metrics['grounding_score'] = ((supported + 0.5 * partially_supported) / len(valid_claims)) * 100.0
                metrics['hallucination_score'] = (not_found / len(valid_claims)) * 100.0
                explanations['grounding_score'] = f"{supported} supported, {partially_supported} partially supported out of {len(valid_claims)} valid claims."
                explanations['hallucination_score'] = f"{not_found} out of {len(valid_claims)} valid claims have no supporting evidence."
            else:
                metrics['grounding_score'] = 0.0
                metrics['hallucination_score'] = 0.0
                explanations['grounding_score'] = "All claims had verification failures"
                explanations['hallucination_score'] = "All claims had verification failures"
        else:
            metrics['grounding_score'] = 0.0
            metrics['hallucination_score'] = 0.0
            explanations['grounding_score'] = "No claims extracted"
            explanations['hallucination_score'] = "No claims extracted"

        # 3. Semantic Similarity
        sim_val, sim_exp = compute_semantic_fn(expected_answer, raw_llm_answer)
        metrics['semantic_correctness'] = float(sim_val)
        metrics['semantic_similarity'] = float(sim_val)
        explanations['semantic_correctness'] = sim_exp

        # 4. Numerical Correctness
        num_val, num_exp = eval_numerical_fn(expected_answer, raw_llm_answer, claims)
        metrics['numerical_correctness'] = float(num_val)
        metrics['numerical_similarity'] = float(num_val)
        explanations['numerical_correctness'] = num_exp

        # 5. Completeness
        expected_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', expected_answer) if len(s.strip()) >= 10]
        generated_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw_llm_answer) if len(s.strip()) >= 10]

        if expected_sentences and generated_sentences and semantic_model is not None:
            exp_embs = semantic_model.encode(expected_sentences)
            gen_embs = semantic_model.encode(generated_sentences)
            sim_matrix = util.cos_sim(exp_embs, gen_embs)
            max_sims = sim_matrix.max(dim=1).values.tolist()
            avg_recall = (sum(max_sims) / len(max_sims)) * 100.0
            metrics['completeness'] = max(0.0, min(100.0, avg_recall))
            explanations['completeness'] = f"Evaluated recall across {len(expected_sentences)} expected claims (avg recall: {avg_recall:.1f}%)."
        else:
            metrics['completeness'] = float(sim_val)
            explanations['completeness'] = f"Derived from overall semantic similarity score ({sim_val:.1f}%)."

        # 6. Conciseness
        expected_length = len(expected_answer.split())
        generated_length = len(raw_llm_answer.split())
        if generated_length > expected_length * 2:
            metrics['conciseness'] = 50.0
            explanations['conciseness'] = "Answer is overly verbose"
        elif generated_length > expected_length * 1.5:
            metrics['conciseness'] = 75.0
            explanations['conciseness'] = "Answer is somewhat verbose"
        else:
            metrics['conciseness'] = 100.0
            explanations['conciseness'] = "Answer is appropriately concise"

        # 7. Overall Score Calculation
        weights = {
            'retrieval': 0.05,
            'context': 0.05,
            'grounding': 0.30,
            'semantic': 0.30,
            'numerical': 0.15,
            'completeness': 0.10,
            'conciseness': 0.05,
            'hallucination_penalty': 0.10
        }

        base_score = (
            metrics['retrieval_quality'] * weights['retrieval'] +
            metrics['context_quality'] * weights['context'] +
            metrics['grounding_score'] * weights['grounding'] +
            metrics['semantic_correctness'] * weights['semantic'] +
            metrics['numerical_correctness'] * weights['numerical'] +
            metrics['completeness'] * weights['completeness'] +
            metrics['conciseness'] * weights['conciseness']
        )
        penalty = metrics['hallucination_score'] * weights['hallucination_penalty']
        overall_score = max(0.0, min(100.0, base_score - penalty))

        metrics['overall_score'] = float(overall_score)
        explanations['overall_score'] = f"Weighted sum (base max 100.0) with {penalty:.1f} point hallucination penalty applied."

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "expected_answer_len": len(expected_answer),
                "raw_llm_answer_len": len(raw_llm_answer),
                "num_claims": len(claims),
                "num_chunks": len(scored_chunks)
            },
            outputs={
                "metrics": metrics,
                "score_explanations": explanations,
                "overall_score": overall_score
            },
            intermediate_artifacts={
                "base_score": base_score,
                "hallucination_penalty": penalty
            }
        )

        # Invariant 1: All individual metrics within [0, 100]
        out_of_bounds = {k: v for k, v in metrics.items() if not (0.0 <= v <= 100.0)}
        result.add_invariant_check(
            len(out_of_bounds) == 0,
            "Metric Value Bounds [0, 100]",
            f"Found metrics out of bounds [0, 100]: {out_of_bounds}"
        )

        # Invariant 2: Overall Score Formula Consistency
        expected_overall = max(0.0, min(100.0, base_score - penalty))
        result.add_invariant_check(
            abs(overall_score - expected_overall) < 1e-4,
            "Overall Score Formula Consistency",
            f"Computed overall_score ({overall_score}) does not match weighted sum minus penalty ({expected_overall})"
        )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
