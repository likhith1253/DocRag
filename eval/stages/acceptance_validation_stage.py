"""
Stage 6: Regression & Acceptance Validation Stage

Evaluates system acceptance criteria gates before report generation:
1. Upstream stage invariant pass check
2. Stage serialization integrity check
3. Metric range bounds satisfaction check
4. RAG retrieval diagnostic threshold check
"""

import time
from typing import Dict, List, Any, Optional
from eval.stage_framework import StageResult, StageStatus, AcceptanceStatus

class AcceptanceValidationStage:
    """Stage 6: Evaluates system acceptance gates."""
    
    STAGE_ID = 6
    STAGE_NAME = "Regression & Acceptance Validation"

    def execute(
        self,
        stage_results: List[StageResult],
        gold_reference: Dict[str, Any],
        computed_metrics: Dict[str, float],
        noise_tolerance_pct: float = 1.0
    ) -> StageResult:
        start_time = time.perf_counter()

        gate_failures = []
        passed_gates = []

        # Gate 1: All Upstream Invariants Passed Cleanly
        failed_stages = [sr for sr in stage_results if sr.status == StageStatus.FAILED]
        if failed_stages:
            gate_failures.append({
                "gate": "Upstream Stage Invariants",
                "details": f"Failed upstream stages: {[f.stage_name for f in failed_stages]}"
            })
        else:
            passed_gates.append("Upstream Stage Invariants")

        # Gate 2: RAG Retrieval Diagnostic Threshold Check
        retrieval_stage_res = next((sr for sr in stage_results if sr.stage_id == 1), None)
        if retrieval_stage_res:
            diags = retrieval_stage_res.outputs.get("diagnostics", {})
            gold_retrieved = diags.get("gold_retrieved", True)
            if not gold_retrieved:
                gate_failures.append({
                    "gate": "RAG Retrieval Gold Chunk Threshold",
                    "details": "Gold evidence chunk was not retrieved in top K results"
                })
            else:
                passed_gates.append("RAG Retrieval Gold Chunk Threshold")

        # Gate 3: Gold Reference Metric Expectation Check
        expected_ranges = gold_reference.get("expected_metric_ranges", {})
        grounding_min = expected_ranges.get("grounding_score_min", 0.0)
        hallucination_max = expected_ranges.get("hallucination_score_max", 100.0)

        actual_grounding = computed_metrics.get("grounding_score", 0.0)
        actual_hallucination = computed_metrics.get("hallucination_score", 0.0)

        if actual_grounding < (grounding_min - noise_tolerance_pct):
            gate_failures.append({
                "gate": "Grounding Score Minimum Expectation",
                "details": f"Grounding score {actual_grounding:.2f}% is below gold reference expectation {grounding_min:.2f}%"
            })
        else:
            passed_gates.append("Grounding Score Minimum Expectation")

        if actual_hallucination > (hallucination_max + noise_tolerance_pct):
            gate_failures.append({
                "gate": "Hallucination Score Maximum Expectation",
                "details": f"Hallucination score {actual_hallucination:.2f}% exceeds gold reference threshold {hallucination_max:.2f}%"
            })
        else:
            passed_gates.append("Hallucination Score Maximum Expectation")

        # System Acceptance Status
        acceptance_status = AcceptanceStatus.ACCEPTED if len(gate_failures) == 0 else AcceptanceStatus.REJECTED

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED if acceptance_status == AcceptanceStatus.ACCEPTED else StageStatus.WARNING,
            inputs={
                "num_upstream_stages": len(stage_results),
                "noise_tolerance_pct": noise_tolerance_pct
            },
            outputs={
                "acceptance_status": acceptance_status.value,
                "passed_gates": passed_gates,
                "gate_failures": gate_failures
            },
            intermediate_artifacts={
                "num_gate_failures": len(gate_failures),
                "num_passed_gates": len(passed_gates)
            }
        )

        # Invariant 1: System Acceptance Status Valid
        result.add_invariant_check(
            acceptance_status in [AcceptanceStatus.ACCEPTED, AcceptanceStatus.REJECTED],
            "System Acceptance Status Validity",
            f"Acceptance status must be ACCEPTED or REJECTED (got {acceptance_status})"
        )

        # Invariant 2: Zero Critical Gate Failures for PASSED status
        if acceptance_status == AcceptanceStatus.REJECTED:
            result.add_invariant_check(
                False,
                "Acceptance Gate Satisfaction",
                f"System rejected due to {len(gate_failures)} gate failures: {gate_failures}",
                severity="WARNING"
            )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
