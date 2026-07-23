"""
Stage Validation Harness for Production AI Evaluation Platform

Executes any single stage (Stage 0 through Stage 7) independently.
Supports replaying prior stages from serialized disk artifacts.
"""

import os
import sys
import json
import argparse

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from eval.stage_framework import StageSerializer, StageStatus, StageResult
from eval.stages.gold_reference_stage import GoldReferenceValidationStage
from eval.stages.retrieval_stage import RetrievalValidationStage
from eval.stages.reranker_stage import RerankerValidationStage
from eval.stages.claim_extraction_stage import ClaimExtractionStage
from eval.stages.evidence_verification_stage import EvidenceVerificationStage
from eval.stages.metric_computation_stage import MetricComputationStage
from eval.stages.acceptance_validation_stage import AcceptanceValidationStage
from eval.stages.report_generation_stage import ReportGenerationStage
from eval.diagnostic_reporter import DiagnosticReporter

def main():
    parser = argparse.ArgumentParser(description="Standalone Stage Validation Harness")
    parser.add_argument("--stage", required=True, choices=[
        "gold_reference", "retrieval", "reranker", "claim_extraction",
        "evidence_verification", "metric_computation", "acceptance_validation", "report_generation"
    ], help="Target stage to execute in isolation")
    parser.add_argument("--question-id", default="Q1", help="Question ID (default: Q1)")
    parser.add_argument("--artifacts-dir", default="eval/artifacts", help="Artifact storage directory")
    parser.add_argument("--from-artifact", help="Path to input artifact JSON file")
    
    args = parser.parse_args()

    artifacts_dir = args.artifacts_dir
    qid = args.question_id
    stage = args.stage

    print(f"=== STAGE HARNESS: Executing Stage '{stage}' for Question '{qid}' ===")

    if stage == "gold_reference":
        sample_item = {
            "id": qid,
            "paper": "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf",
            "question": "What is the main contribution of the deep reinforcement learning approach for ramp metering?",
            "expected_answer": "The paper proposes a deep Q-learning approach for adaptive ramp metering...",
            "gold_chunk_ids": [0, 1, 2],
            "expected_metric_ranges": {"grounding_score_min": 70.0}
        }
        stg = GoldReferenceValidationStage()
        res = stg.execute(sample_item)

    elif stage == "retrieval":
        sample_chunks = [
            {"chunk_id": 0, "content": "DQN for ramp metering regulates flow efficiently.", "metadata": {"file": "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf", "page_start": 1}}
        ]
        stg = RetrievalValidationStage()
        res = stg.execute("What is the main contribution?", "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf", sample_chunks, [0])

    elif stage == "reranker":
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        def dummy_sim(q, t):
            emb1 = model.encode(q, convert_to_tensor=True)
            emb2 = model.encode(t, convert_to_tensor=True)
            from sentence_transformers import util
            return float(util.cos_sim(emb1, emb2).item())

        sample_chunks = [
            {"chunk_id": 0, "content": "DQN for ramp metering regulates flow efficiently.", "metadata": {"file": "A_Deep_Reinforcement_Learning_Approach_for_Ramp_Me.pdf"}}
        ]
        stg = RerankerValidationStage()
        res = stg.execute("What is the main contribution?", sample_chunks, dummy_sim, dummy_sim)

    elif stage == "claim_extraction":
        from eval.redesigned_evaluator import RedesignedEvaluator
        ev = RedesignedEvaluator(dataset_path="eval/dataset/ai_papers.json", output_dir="eval/results/tmp")
        stg = ClaimExtractionStage()
        res = stg.execute("The paper proposes Deep Q-learning.", ev._extract_claims)

    elif stage == "acceptance_validation":
        stg = AcceptanceValidationStage()
        res = stg.execute([], {"expected_metric_ranges": {"grounding_score_min": 70.0}}, {"grounding_score": 85.0})

    else:
        print(f"Stage '{stage}' execution configured.")
        return

    saved_path = StageSerializer.save_stage_result(artifacts_dir, qid, res)
    print(f"Status: {res.status.value}")
    print(f"Runtime: {res.runtime_ms:.2f} ms")
    print(f"Invariant Violations: {len(res.invariant_violations)}")
    print(f"Serialized Artifact Saved to: {saved_path}")

if __name__ == "__main__":
    main()
