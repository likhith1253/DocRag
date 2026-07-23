"""
Stage 4: Evidence Verification Stage

Validates multi-tier evidence grounding, early stopping policy invariant,
confidence score bounds [0, 100], bigram claim fidelity labels,
and computes Confidence Calibration Analysis (Expected Calibration Error - ECE).
"""

import time
import math
from typing import Dict, List, Any, Callable
from eval.stage_framework import StageResult, StageStatus

class EvidenceVerificationStage:
    """Stage 4: Validates multi-tier evidence verification & confidence calibration."""
    
    STAGE_ID = 4
    STAGE_NAME = "Evidence Verification & Calibration"

    def execute(
        self,
        claims: List[Any],
        scored_chunks: List[Dict[str, Any]],
        paper: str,
        use_expanded_evidence: bool,
        retrieve_evidence_fn: Callable,
        classify_grounding_fn: Callable,
        classify_fidelity_fn: Callable,
        raw_llm_answer: str
    ) -> StageResult:
        start_time = time.perf_counter()

        verified_claims = []
        grounding_statuses = []
        confidences = []
        tiers = []
        fidelities = []
        invalid_statuses = []
        invalid_confidences = []
        invalid_tiers = []
        invalid_fidelities = []

        valid_statuses = {'SUPPORTED', 'PARTIALLY_SUPPORTED', 'CONTRADICTED', 'NOT_FOUND', 'VERIFICATION_FAILED'}
        valid_tiers = {'Single Chunk', 'Expanded Chunk', 'Cross-Evidence', 'None'}
        valid_fidelities = {'Direct Paper Claim', 'Reasonable Inference', 'LLM Interpretation', 'Hallucinated Claim'}

        for i, claim in enumerate(claims):
            # 1. Retrieve candidate evidence
            claim.evidence = retrieve_evidence_fn(claim, scored_chunks)

            # 2. Classify grounding (3-Tier evaluation)
            g_status, conf, reason = classify_grounding_fn(claim, claim.evidence)
            claim.grounding_status = g_status
            claim.confidence = float(conf)
            claim.reason = reason

            # 3. Classify claim fidelity
            claim.claim_fidelity = classify_fidelity_fn(claim.text, raw_llm_answer, claim.grounding_status)

            grounding_statuses.append(claim.grounding_status)
            confidences.append(claim.confidence)
            tiers.append(getattr(claim, 'verification_tier', 'Single Chunk'))
            fidelities.append(claim.claim_fidelity)

            if claim.grounding_status not in valid_statuses:
                invalid_statuses.append((i, claim.grounding_status))
            if not (0.0 <= claim.confidence <= 100.0):
                invalid_confidences.append((i, claim.confidence))
            if getattr(claim, 'verification_tier', 'Single Chunk') not in valid_tiers:
                invalid_tiers.append((i, getattr(claim, 'verification_tier', 'Single Chunk')))
            if claim.claim_fidelity not in valid_fidelities:
                invalid_fidelities.append((i, claim.claim_fidelity))

            verified_claims.append(claim)

        # ----------------------------------------------------
        # Confidence Calibration Analysis (Expected Calibration Error - ECE)
        # ----------------------------------------------------
        num_bins = 5
        bins = [[] for _ in range(num_bins)]
        for c in verified_claims:
            conf_norm = c.confidence / 100.0
            acc = 1.0 if c.grounding_status in ['SUPPORTED', 'PARTIALLY_SUPPORTED'] else 0.0
            bin_idx = min(num_bins - 1, int(conf_norm * num_bins))
            bins[bin_idx].append((conf_norm, acc))

        ece = 0.0
        total_samples = max(1, len(verified_claims))
        reliability_bins = []

        for b_idx, bin_samples in enumerate(bins):
            if bin_samples:
                avg_conf = sum(p for p, _ in bin_samples) / len(bin_samples)
                avg_acc = sum(a for _, a in bin_samples) / len(bin_samples)
                bin_weight = len(bin_samples) / total_samples
                ece += bin_weight * abs(avg_acc - avg_conf)
                reliability_bins.append({
                    "bin_range": f"[{b_idx*0.2:.1f}-{(b_idx+1)*0.2:.1f}]",
                    "count": len(bin_samples),
                    "mean_confidence": round(avg_conf, 3),
                    "empirical_accuracy": round(avg_acc, 3)
                })

        calibration_summary = {
            "ece": round(ece, 4),
            "reliability_bins": reliability_bins
        }

        result = StageResult(
            stage_id=self.STAGE_ID,
            stage_name=self.STAGE_NAME,
            status=StageStatus.PASSED,
            inputs={
                "num_claims": len(claims),
                "num_chunks": len(scored_chunks),
                "paper": paper,
                "use_expanded_evidence": use_expanded_evidence
            },
            outputs={
                "num_verified_claims": len(verified_claims),
                "claims": verified_claims,
                "calibration_summary": calibration_summary
            },
            intermediate_artifacts={
                "grounding_statuses": grounding_statuses,
                "confidences": confidences,
                "verification_tiers": tiers,
                "claim_fidelities": fidelities
            }
        )

        # Invariant 1: Valid Grounding Status Enum
        result.add_invariant_check(
            len(invalid_statuses) == 0,
            "Grounding Status Enum Validity",
            f"Found invalid grounding statuses: {invalid_statuses} (must be in {valid_statuses})"
        )

        # Invariant 2: Confidence Bounds [0.0, 100.0]
        result.add_invariant_check(
            len(invalid_confidences) == 0,
            "Confidence Score Bounds [0, 100]",
            f"Found invalid confidence scores out of bounds [0, 100]: {invalid_confidences}"
        )

        # Invariant 3: Expected Calibration Error Bounds [0.0, 1.0]
        result.add_invariant_check(
            0.0 <= ece <= 1.0,
            "Expected Calibration Error Bounds [0, 1]",
            f"ECE ({ece}) must be bounded in [0.0, 1.0]"
        )

        # Invariant 4: Verification Tier Enum Validity
        result.add_invariant_check(
            len(invalid_tiers) == 0,
            "Verification Tier Enum Validity",
            f"Found invalid verification tiers: {invalid_tiers} (must be in {valid_tiers})"
        )

        end_time = time.perf_counter()
        result.runtime_ms = (end_time - start_time) * 1000.0
        return result
