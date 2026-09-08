"""
Unit tests for Phase 4: Reliability + Performance + Production Hardening.
Covers:
  1. DevicePolicyManager (CUDA unavailable, insufficient VRAM, sufficient VRAM, GPU failure fallback)
  2. QueryEmbeddingCache & CrossEncoderScoreCache (hit, miss, LRU bounding)
  3. Retrieval candidate bounding without breaking evidence coverage
  4. Context excerpt boundary budgeting preserving complete equations/tables/algorithms
  5. Canonical graceful failure handling (Embedding, Qdrant, LLM timeout, Empty retrieval)
  6. Query profiling and stage timing generation
"""

import os
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

from storage.device_policy import DevicePolicyManager
from storage.vector_store import QueryEmbeddingCache
from retrieval.cross_encoder_rerank import CrossEncoderScoreCache
from agents.doc_agent import _budget_excerpt_boundary, CANNOT_FIND_RESPONSE
from agents.orchestrator import _ensure_evidence_coverage, answer


class TestDevicePolicyManager(unittest.TestCase):
    """Test device selection logic for CPU-first execution and GPU readiness."""

    def test_cuda_unavailable_selects_cpu(self):
        with patch.object(DevicePolicyManager, "_check_cuda_available", return_value=False):
            manager = DevicePolicyManager(safe_margin_mb=3500)
            emb_dev, reason_emb = manager.get_embedding_device("cuda")
            self.assertEqual(emb_dev, "cpu")
            self.assertIn("CUDA unavailable", reason_emb)

            ce_dev, reason_ce = manager.get_reranker_device("cuda")
            self.assertEqual(ce_dev, "cpu")
            self.assertIn("CUDA unavailable", reason_ce)

            llm_dev, reason_llm = manager.get_llm_device("cuda")
            self.assertEqual(llm_dev, "cpu")

    def test_cuda_insufficient_vram_selects_cpu(self):
        # 16 GB GPU with only 2000 MB free (< 3500 MB safe margin)
        with patch.object(DevicePolicyManager, "_check_cuda_available", return_value=True), \
             patch.object(DevicePolicyManager, "_get_cuda_memory_mb", return_value=(2000.0, 16000.0)):
            manager = DevicePolicyManager(safe_margin_mb=3500)
            emb_dev, reason = manager.get_embedding_device("cuda")
            self.assertEqual(emb_dev, "cpu")
            self.assertIn("insufficient safe GPU memory", reason)

            ce_dev, reason_ce = manager.get_reranker_device("cuda")
            self.assertEqual(ce_dev, "cpu")
            self.assertIn("insufficient safe GPU memory", reason_ce)

            # LLM is primary workload: should still be assigned to cuda if available
            llm_dev, _ = manager.get_llm_device("cuda")
            self.assertEqual(llm_dev, "cuda")

    def test_cuda_sufficient_vram_selects_gpu(self):
        # 16 GB V100 with 10000 MB free (> 3500 MB safe margin)
        with patch.object(DevicePolicyManager, "_check_cuda_available", return_value=True), \
             patch.object(DevicePolicyManager, "_get_cuda_memory_mb", return_value=(10000.0, 16000.0)):
            manager = DevicePolicyManager(safe_margin_mb=3500)
            emb_dev, reason = manager.get_embedding_device("cuda")
            self.assertEqual(emb_dev, "cuda")
            self.assertIn("safe GPU memory available", reason)

            ce_dev, _ = manager.get_reranker_device("cuda")
            self.assertEqual(ce_dev, "cuda")

    def test_gpu_init_failure_fallback_to_cpu(self):
        from storage.vector_store import _load_with_gpu_fallback

        def failing_loader(device):
            if device == "cuda":
                raise RuntimeError("CUDA out of memory or driver error")
            return f"ModelOn({device})"

        model, actual_device = _load_with_gpu_fallback("TestEncoder", "mock-model", "cuda", failing_loader)
        self.assertEqual(actual_device, "cpu")
        self.assertEqual(model, "ModelOn(cpu)")


class TestEmbeddingAndCrossEncoderCache(unittest.TestCase):
    """Test LRU bounded caches for query embeddings and cross-encoder scores."""

    def test_query_embedding_cache_hit_miss_and_bounding(self):
        cache = QueryEmbeddingCache(max_size=3)
        vec1 = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        vec2 = np.array([0.4, 0.5, 0.6], dtype=np.float32)
        vec3 = np.array([0.7, 0.8, 0.9], dtype=np.float32)
        vec4 = np.array([1.0, 1.1, 1.2], dtype=np.float32)

        # First query -> miss
        self.assertIsNone(cache.get("modelA", "query 1"))
        self.assertEqual(cache.misses, 1)

        # Put query 1 -> hit on retrieval
        cache.put("modelA", "query 1", vec1)
        res = cache.get("modelA", "query 1")
        self.assertIsNotNone(res)
        np.testing.assert_array_equal(res, vec1)
        self.assertEqual(cache.hits, 1)

        # Put 2 more items (cache full at 3)
        cache.put("modelA", "query 2", vec2)
        cache.put("modelA", "query 3", vec3)
        self.assertEqual(len(cache._cache), 3)

        # Access query 1 so it becomes most recently used
        self.assertIsNotNone(cache.get("modelA", "query 1"))

        # Adding 4th item evicts the oldest untouched item (query 2)
        cache.put("modelA", "query 4", vec4)
        self.assertEqual(len(cache._cache), 3)
        # Cache should have query 3, query 1, query 4
        self.assertIsNotNone(cache.get("modelA", "query 1"))
        self.assertIsNone(cache.get("modelA", "query 2"))  # Evicted!

    def test_cross_encoder_score_cache(self):
        ce_cache = CrossEncoderScoreCache(max_size=2)
        self.assertIsNone(ce_cache.get("query", "hash1"))
        self.assertEqual(ce_cache.misses, 1)

        ce_cache.put("query", "hash1", 4.5)
        self.assertEqual(ce_cache.get("query", "hash1"), 4.5)
        self.assertEqual(ce_cache.hits, 1)

        ce_cache.put("query", "hash2", 3.2)
        ce_cache.put("query", "hash3", 5.1)  # Evicts hash1
        self.assertEqual(len(ce_cache._cache), 2)
        self.assertIsNone(ce_cache.get("query", "hash1"))


class TestRetrievalCandidateBounding(unittest.TestCase):
    """Verify that bounding reranker candidates does not break evidence coverage."""

    def test_ensure_evidence_coverage_restores_from_candidate_pool(self):
        # Candidate pool has 10 items; rank 9 has the essential equation
        candidate_pool = [
            {"id": f"chunk_{i}", "content": f"Generic RL text without math {i}", "score": 10.0 - i, "metadata": {"hash": f"h_{i}"}}
            for i in range(8)
        ]
        eq_chunk = {
            "id": "eq_chunk",
            "content": r"Algorithm 1 One-step Q-learning: y = r + \gamma \max_{a'} Q(s', a'; \theta^-)",
            "score": 1.5,
            "metadata": {"hash": "h_eq", "contains_equation": True, "contains_algorithm": True}
        }
        candidate_pool.append(eq_chunk)

        # Initial top 4 output chunks have no equations
        initial_output = list(candidate_pool[:4])
        self.assertFalse(any(c["id"] == "eq_chunk" for c in initial_output))

        # Run _ensure_evidence_coverage for equation intent
        intent = {"equation": True, "table": False, "figure": False, "algorithm": True}
        restored = _ensure_evidence_coverage(
            candidate_pool,
            initial_output,
            intent,
            question="What is the one-step Q-learning target equation in Algorithm 1?"
        )

        # Equation chunk must be restored
        self.assertTrue(any(c["id"] == "eq_chunk" for c in restored))
        # Total output count must remain bounded (same length as initial_output)
        self.assertEqual(len(restored), len(initial_output))


class TestPromptBudgeting(unittest.TestCase):
    """Verify excerpt boundary budgeting preserves complete equations and tables."""

    def test_budget_excerpt_boundary_preserves_equations(self):
        text = (
            "The update rule is defined as follows:\n\n"
            r"\[ J(\pi) = \sum_{t=0}^T \mathbb{E}_{(s_t, a_t) \sim \rho_\pi} [r(s_t, a_t) + \alpha \mathcal{H}(\pi(\cdot|s_t))] \]"
            "\n\nwhere alpha is the temperature parameter controlling entropy."
        )
        # Budget slightly less than full length to test boundary clipping
        budget = len(text) - 15
        budgeted = _budget_excerpt_boundary(text, budget)
        # Equation must not be truncated in the middle
        self.assertIn(r"J(\pi)", budgeted)
        self.assertIn(r"\mathcal{H}(\pi(\cdot|s_t))", budgeted)


class TestGracefulFailureHandling(unittest.TestCase):
    """Verify canonical failure responses when infrastructure components fail."""

    @patch("agents.orchestrator.app.invoke")
    def test_embedding_failure_canonical_response(self, mock_invoke):
        mock_invoke.side_effect = RuntimeError("Embedding service unavailable: Connection refused")
        ans, bd, chunks, citations = answer("What is DQN?")
        self.assertEqual(ans, "Embedding service unavailable.")
        self.assertEqual(chunks, [])
        self.assertEqual(citations, [])

    @patch("agents.orchestrator.app.invoke")
    def test_qdrant_failure_canonical_response(self, mock_invoke):
        mock_invoke.side_effect = RuntimeError("Vector search failed: Collection not found")
        ans, bd, chunks, citations = answer("What is DQN?")
        self.assertEqual(ans, "Vector search failed.")
        self.assertEqual(chunks, [])

    @patch("agents.orchestrator.app.invoke")
    def test_llm_timeout_canonical_response(self, mock_invoke):
        mock_invoke.side_effect = TimeoutError("Request timed out after 120 seconds")
        ans, bd, chunks, citations = answer("What is DQN?")
        self.assertEqual(ans, "LLM generation timed out.")

    def test_empty_retrieval_canonical_response(self):
        from agents.orchestrator import agent_node
        state = {
            "request_id": "test_req",
            "question": "Nonexistent topic",
            "retrieved_chunks": [],
            "error": "Zero chunks retrieved",
            "latency_breakdown": {}
        }
        res = agent_node(state)
        self.assertEqual(res["answer"], CANNOT_FIND_RESPONSE)


class TestQueryProfiling(unittest.TestCase):
    """Verify stage timing information and query profiling record generation."""

    def test_query_profile_logging(self):
        from storage.pipeline_logger import log_query_profile, QUERY_PROFILE_LOG_PATH
        import json

        test_record = {
            "request_id": "test_req_phase4",
            "timestamp": "2026-09-08T12:00:00Z",
            "collection": "test_col",
            "query": "Test profiling query",
            "requested_papers": ["DQN"],
            "retrieved_papers": ["DQN"],
            "embedding_device": "cpu",
            "reranker_device": "cpu",
            "llm_device": "cpu",
            "retrieval_candidate_count": 20,
            "reranker_candidate_count": 15,
            "final_evidence_count": 5,
            "evidence_types": ["equation"],
            "query_analysis_ms": 1.2,
            "paper_matching_ms": 0.8,
            "embedding_ms": 15.3,
            "qdrant_ms": 4.1,
            "filtering_ms": 0.5,
            "mmr_ms": 2.2,
            "reranker_ms": 18.4,
            "evidence_selection_ms": 0.9,
            "prompt_builder_ms": 3.1,
            "llm_ms": 120.5,
            "verifier_ms": 5.0,
            "formatting_ms": 1.1,
            "total_ms": 173.1,
            "verifier_status": "PASSED"
        }

        log_query_profile(test_record)

        self.assertTrue(QUERY_PROFILE_LOG_PATH.exists())
        with open(QUERY_PROFILE_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertTrue(len(lines) > 0)
        last_entry = json.loads(lines[-1])
        self.assertEqual(last_entry["request_id"], "test_req_phase4")
        self.assertEqual(last_entry["verifier_status"], "PASSED")
        self.assertEqual(last_entry["total_ms"], 173.1)


if __name__ == "__main__":
    unittest.main()
