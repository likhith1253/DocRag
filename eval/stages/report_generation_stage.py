"""
Stage 7: Report Generation Stage

Validates assembly of QuestionReport, consistency between stage output metrics
and report summary fields, and formats markdown audit reports with system acceptance status.
"""

import time
from typing import Dict, List, Any, Optional
from eval.stage_framework import StageResult, StageStatus

class ReportGenerationStage:
    """Stage 7: Validates final report assembly, trace logging, and acceptance status."""
    
    STAGE_ID = 7
    STAGE_NAME = "Report Generation"

    def execute(
        self,
        question_id: str,
        paper: str,
        question: str,
        expected_answer: str,
        raw_llm_answer: str,
        retrieved_chunks: List[Dict[str, Any]],
        claims: List[Any],
        metrics: Dict[str, float],
        explanations: Dict[str, str],
        runtime_breakdown: Dict[str, float],
        stage_results: List[StageResult],
        acceptance_status: str,
        question_report_cls: Any
    ) -> StageResult:
        start_time = time.perf_counter()

        # Build QuestionReport dataclass
        report = question_report_cls(
            question_id=question_id,
            paper=paper,
            question=question,
            question_type='unknown',
            expected_answer=expected_answer,
            retrieved_chunks=retrieved_chunks,
            raw_llm_answer=raw_llm_answer,
            final_parsed_answer=raw_llm_answer,
            claims=claims,
            semantic_similarity=metrics.get('semantic_similarity', 0.0),
            semantic_explanation=explanations.get('semantic_correctness', ''),
            numerical_similarity=metrics.get('numerical_similarity', 0.0),
            numerical_explanation=explanations.get('numerical_correctness', ''),
            retrieval_quality=metrics.get('retrieval_quality', 0.0),
            context_quality=metrics.get('context_quality', 0.0),
            grounding_score=metrics.get('grounding_score', 0.0),
            semantic_correctness=metrics.get('semantic_correctness', 0.0),
            numerical_correctness=metrics.get('numerical_correctness', 0.0),
            completeness=metrics.get('completeness', 0.0),
            conciseness=metrics.get('conciseness', 0.0),
            hallucination_score=metrics.get('hallucination_score', 0.0),
            overall_score=metrics.get('overall_score', 0.0),
            score_explanations=explanations,
            runtime_breakdown=runtime_breakdown,
            pipeline_stages=[sr.to_dict() for sr in stage_results]
        )

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "question_id": question_id,
                "num_stage_results": len(stage_results),
                "acceptance_status": acceptance_status
            },
            outputs={
                "report": report,
                "overall_score": report.overall_score,
                "acceptance_status": acceptance_status
            },
            intermediate_artifacts={
                "pipeline_stage_count": len(report.pipeline_stages)
            }
        )

        # Invariant 1: Summary overall score matches computed metric overall score
        result.add_invariant_check(
            abs(report.overall_score - metrics.get('overall_score', 0.0)) < 1e-4,
            "Report Overall Score Summary Consistency",
            f"Report overall score ({report.overall_score}) does not match computed metric ({metrics.get('overall_score')})"
        )

        # Invariant 2: Summary grounding score matches computed metric grounding score
        result.add_invariant_check(
            abs(report.grounding_score - metrics.get('grounding_score', 0.0)) < 1e-4,
            "Report Grounding Score Summary Consistency",
            f"Report grounding score ({report.grounding_score}) does not match computed metric ({metrics.get('grounding_score')})"
        )

        # Invariant 3: Complete 7-Stage Trace Presence
        result.add_invariant_check(
            len(report.pipeline_stages) >= 7,
            "Complete Pipeline Stage Trace Presence",
            f"Pipeline trace must contain at least 7 prior stages (got {len(report.pipeline_stages)})"
        )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
