"""
Diagnostic Reporter for Production AI Evaluation Platform

Pinpoints the FIRST failing stage (root cause analysis), renders the 8-Stage metric dependency graph,
and generates subsystem diagnostic & acceptance reports.
"""

from typing import List, Dict, Any, Optional
from eval.stage_framework import StageResult, StageStatus

METRIC_DEPENDENCY_GRAPH = """
========================================================================================================
PRODUCTION AI EVALUATION PLATFORM - 8-STAGE DEPENDENCY GRAPH
========================================================================================================

 [Stage 0: Gold Ref] -------------> (Semantic Gold Claims & Metric Bounds)
         │                                       │
 [Stage 1: Retrieval Diag] -------> (Recall@K, MRR, nDCG, Gold Chunk Rank)
         │                                       │
 [Stage 2: Rerank Diag] ----------> (scored_chunks)
         │                                       │
 [Stage 3: Canonical Claims] -----> (CanonicalClaimSet: claim_001_a8f3b)
         │                                       │
 [Stage 4: Evidence & ECE] -------> (verified_claims & Calibration ECE) ───┐
                                                                            │
 [Stage 5: Metric Computation] <-- (8 Bounded Metrics & Overall Score) ────┤
         │                                                                  │
 [Stage 6: Acceptance Gates]   <-- (AcceptanceStatus: ACCEPTED / REJECTED) ─┘
         │
 [Stage 7: Report Generation]  <-- (QuestionReport & Markdown Audit Report)
========================================================================================================
"""

class DiagnosticReporter:
    """Diagnostic reporter for identifying first failing stage, metric dependencies, and acceptance gates."""

    @staticmethod
    def get_first_failing_stage(stage_results: List[StageResult]) -> Optional[StageResult]:
        """Scans stage results in order and returns the FIRST failing or warning stage."""
        for sr in stage_results:
            if sr.status == StageStatus.FAILED:
                return sr
        for sr in stage_results:
            if sr.status == StageStatus.WARNING:
                return sr
        return None

    @classmethod
    def generate_diagnostic_summary(cls, question_id: str, stage_results: List[StageResult]) -> str:
        first_failing = cls.get_first_failing_stage(stage_results)
        
        lines = []
        lines.append(f"=== DIAGNOSTIC REPORT: Question {question_id} ===")
        lines.append("")
        
        if first_failing:
            lines.append(f"FIRST FAILING/WARNING STAGE: Stage {first_failing.stage_id} - {first_failing.stage_name}")
            lines.append(f"Status: {first_failing.status.value if hasattr(first_failing.status, 'value') else str(first_failing.status)}")
            lines.append("Invariant Violations:")
            for inv in first_failing.invariant_violations:
                lines.append(f"  - [{inv.get('severity', 'ERROR')}] {inv.get('name')}: {inv.get('details')}")
            for err in first_failing.error_messages:
                lines.append(f"  - Error: {err}")
        else:
            lines.append("ALL STAGES PASSED CLEANLY (Zero Invariant Violations)")

        lines.append("")
        lines.append("STAGE EXECUTION SUMMARY:")
        lines.append("| Stage ID | Stage Name | Status | Runtime (ms) | Invariant Violations |")
        lines.append("|---|---|---|---|---|")
        for sr in stage_results:
            status_str = sr.status.value if hasattr(sr.status, 'value') else str(sr.status)
            lines.append(f"| Stage {sr.stage_id} | {sr.stage_name} | {status_str} | {sr.runtime_ms:.2f} | {len(sr.invariant_violations)} |")

        lines.append("")
        lines.append(METRIC_DEPENDENCY_GRAPH)
        return "\n".join(lines)
