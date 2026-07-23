"""
Automated Invariant Test Suite for Production AI Evaluation Platform

Tests mathematical bounds, RAG retrieval diagnostics, ECE calibration,
canonical claim sets, provenance versioning, acceptance gates, and stage isolation across Stages 0-7.
"""

import unittest
import os
import json
import tempfile
import shutil

from eval.stage_framework import StageResult, StageStatus, AcceptanceStatus, StageSerializer
from eval.stages.gold_reference_stage import GoldReferenceValidationStage
from eval.stages.retrieval_stage import RetrievalValidationStage
from eval.stages.reranker_stage import RerankerValidationStage
from eval.stages.claim_extraction_stage import ClaimExtractionStage
from eval.stages.evidence_verification_stage import EvidenceVerificationStage
from eval.stages.metric_computation_stage import MetricComputationStage
from eval.stages.acceptance_validation_stage import AcceptanceValidationStage
from eval.stages.report_generation_stage import ReportGenerationStage
from eval.diagnostic_reporter import DiagnosticReporter
from eval.regression_tester import RegressionTester

class TestStageInvariants(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_stage_0_gold_reference_semantic_expectations(self):
        stage = GoldReferenceValidationStage()

        # Valid item with semantic expectations
        item_valid = {
            "id": "Q1",
            "paper": "paper.pdf",
            "question": "What is the contribution?",
            "expected_answer": "This paper introduces a novel algorithm.",
            "gold_chunk_ids": [0, 1],
            "expected_metric_ranges": {"grounding_score_min": 70.0}
        }
        res_valid = stage.execute(item_valid)
        self.assertEqual(res_valid.status, StageStatus.PASSED)
        self.assertEqual(len(res_valid.invariant_violations), 0)
        self.assertIn("gold_chunk_ids", res_valid.outputs)

    def test_stage_1_retrieval_diagnostics(self):
        stage = RetrievalValidationStage()
        chunks = [
            {"chunk_id": 0, "content": "Text chunk 1", "metadata": {"file": "paper.pdf"}}
        ]
        res = stage.execute("question text", "paper.pdf", chunks, gold_chunk_ids=[0])
        self.assertEqual(res.status, StageStatus.PASSED)
        
        diags = res.outputs["diagnostics"]
        self.assertTrue(diags["gold_retrieved"])
        self.assertEqual(diags["mrr"], 1.0)
        self.assertIn("recall_at_1", diags["recall_at_k"])

    def test_stage_2_reranker_bounds(self):
        stage = RerankerValidationStage()
        chunks = [
            {"content": "Sample text", "metadata": {"file": "paper.pdf"}}
        ]
        dummy_sim = lambda q, t: 0.85
        dummy_rerank = lambda q, t: 2.5

        res = stage.execute("query", chunks, dummy_sim, dummy_rerank)
        self.assertEqual(res.status, StageStatus.PASSED)
        
        norm = res.outputs["scored_chunks"][0]["normalized_score"]
        self.assertTrue(0.0 <= norm <= 1.0)

    def test_stage_3_canonical_claim_set(self):
        stage = ClaimExtractionStage()
        
        class DummyClaim:
            def __init__(self, text, ctype):
                self.text = text
                self.claim_type = ctype

        dummy_extractor = lambda ans: [DummyClaim("DQN is used.", "factual")]
        res = stage.execute("The paper uses DQN.", dummy_extractor)
        self.assertEqual(res.status, StageStatus.PASSED)
        self.assertIn("canonical_claim_set", res.outputs)
        self.assertEqual(len(res.outputs["canonical_claim_set"]), 1)
        self.assertTrue(res.outputs["canonical_claim_set"][0]["canonical_id"].startswith("claim_"))

    def test_stage_4_ece_calibration(self):
        stage = EvidenceVerificationStage()
        
        class DummyClaim:
            def __init__(self, text):
                self.text = text
                self.evidence = []
                self.grounding_status = "SUPPORTED"
                self.confidence = 90.0
                self.claim_fidelity = "Direct Paper Claim"
                self.verification_tier = "Single Chunk"

        dummy_claims = [DummyClaim("Claim 1"), DummyClaim("Claim 2")]
        dummy_retrieve = lambda c, s: []
        dummy_ground = lambda c, e: ("SUPPORTED", 90.0, "Reason")
        dummy_fid = lambda t, a, s: "Direct Paper Claim"

        res = stage.execute(dummy_claims, [], "paper.pdf", True, dummy_retrieve, dummy_ground, dummy_fid, "Answer")
        self.assertEqual(res.status, StageStatus.PASSED)
        self.assertIn("calibration_summary", res.outputs)
        ece = res.outputs["calibration_summary"]["ece"]
        self.assertTrue(0.0 <= ece <= 1.0)

    def test_stage_6_acceptance_validation(self):
        stage = AcceptanceValidationStage()
        
        gold_ref = {"expected_metric_ranges": {"grounding_score_min": 70.0, "hallucination_score_max": 20.0}}
        metrics = {"grounding_score": 85.0, "hallucination_score": 5.0}
        
        res = stage.execute([], gold_ref, metrics)
        self.assertEqual(res.outputs["acceptance_status"], AcceptanceStatus.ACCEPTED.value)

    def test_artifact_provenance_serialization(self):
        res = StageResult(
            stage_id=1,
            stage_name="Retrieval Diagnostics",
            status=StageStatus.PASSED,
            inputs={"q": "test"},
            outputs={"count": 5}
        )
        saved_path = StageSerializer.save_stage_result(self.tmp_dir, "Q1", res)
        self.assertTrue(os.path.exists(saved_path))

        loaded = StageSerializer.load_stage_result(self.tmp_dir, "Q1", 1, "Retrieval Diagnostics")
        self.assertIsNotNone(loaded)
        self.assertIn("git_commit", loaded.provenance)
        self.assertEqual(loaded.provenance["embedding_model"], "all-MiniLM-L6-v2")


if __name__ == "__main__":
    unittest.main()
