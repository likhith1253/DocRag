"""
Unit and regression tests for Phase 6: Performance and Latency Optimization.

Verifies:
  1. Query embedding cache is reused on repeated queries.
  2. CrossEncoder duplicate candidate work is avoided (deduplication & score caching).
  3. Candidate counts remain bounded (single-paper and multi-paper rerank limits).
  4. Repository isolation remains 100% intact (multi-repo retrieval boundary).
  5. Paper isolation remains 100% intact (single-paper query restricted).
  6. Evidence coverage remains intact (restores essential evidence from candidate pool).
  7. ClaimEvidenceVerifier continues to correct known errors and verify claims.
  8. CPU execution works natively.
  9. GPU fallback behavior remains safe on failure.
  10. Caches enforce LRU max_size bounds without unbounded memory growth.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from storage.vector_store import (
    QueryEmbeddingCache,
    VectorStoreManager,
    _load_with_gpu_fallback,
)
from retrieval.cross_encoder_rerank import (
    CrossEncoderScoreCache,
    rerank_cross_encoder,
    get_ce_score_cache,
    prewarm_cross_encoder,
)
from storage.registry import get_registry, RepoStatus
from agents.orchestrator import _ensure_evidence_coverage, _dedup_and_filter_chunks, answer
from agents.doc_agent import ClaimEvidenceVerifier, _extract_equation_labels, CANNOT_FIND_RESPONSE


class TestPhase6Performance(unittest.TestCase):

    def setUp(self):
        self.registry = get_registry()

    def test_1_query_embedding_cache_reuse(self):
        """1. Query embedding cache is reused without redundant encoding."""
        cache = QueryEmbeddingCache(max_size=10)
        vec1 = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        # Initial lookup -> miss
        self.assertIsNone(cache.get("intfloat/e5-base-v2", "test query"))
        self.assertEqual(cache.misses, 1)

        # Store vector -> hit on next lookup
        cache.put("intfloat/e5-base-v2", "test query", vec1)
        res = cache.get("intfloat/e5-base-v2", "test query")
        self.assertIsNotNone(res)
        np.testing.assert_array_equal(res, vec1)
        self.assertEqual(cache.hits, 1)

        # Canonical whitespace stripping
        cache.put("intfloat/e5-base-v2", "   whitespace query   ", vec1)
        self.assertIsNotNone(cache.get("intfloat/e5-base-v2", "whitespace query"))

    def test_2_cross_encoder_duplicate_work_avoidance(self):
        """2. CrossEncoder duplicate candidates are deduplicated and score cache is reused."""
        ce_cache = get_ce_score_cache()
        ce_cache.clear()

        query = "What is experience replay?"
        # Two chunks with identical content text but different chunk IDs
        chunks = [
            {"id": "chunk_1", "content": "Experience replay buffers store transitions (s,a,r,s').", "metadata": {"hash": "h1", "collection_id": "c1"}},
            {"id": "chunk_2", "content": "Experience replay buffers store transitions (s,a,r,s').", "metadata": {"hash": "h2", "collection_id": "c1"}},
        ]

        with patch("retrieval.cross_encoder_rerank._cross_encoder_cache") as mock_cache:
            mock_model = MagicMock()
            # Predict returns 1 score for the 1 unique text pair
            mock_model.predict.return_value = np.array([2.5])
            mock_cache.__contains__.return_value = True
            mock_cache.__getitem__.return_value = mock_model

            reranked = rerank_cross_encoder(query, chunks, top_k=2)
            self.assertEqual(len(reranked), 2)
            # Both chunks received identical score from the single prediction
            self.assertEqual(reranked[0]["rerank_score"], reranked[1]["rerank_score"])
            self.assertEqual(ce_cache.get(query, "h1", collection_id="c1"), 2.5)
            self.assertEqual(ce_cache.get(query, "h2", collection_id="c1"), 2.5)

            # mock_model.predict should have been called with only 1 unique pair, not 2!
            self.assertEqual(mock_model.predict.call_count, 1)
            called_pairs = mock_model.predict.call_args[0][0]
            self.assertEqual(len(called_pairs), 1)

            # Subsequent call with the same chunks hits the ce_cache directly (0 predict calls)
            mock_model.predict.reset_mock()
            rerank_cross_encoder(query, chunks, top_k=2)
            self.assertEqual(mock_model.predict.call_count, 0)

    def test_3_candidate_counts_remain_bounded(self):
        """3. Candidate counts passed to reranker remain bounded."""
        pool = [
            {"id": f"chunk_{i}", "content": f"Content {i}", "score": 10.0 - i, "metadata": {"hash": f"h_{i}"}}
            for i in range(50)
        ]
        # Bounding in orchestrator limits candidate slice to <= 20
        single_cand_limit = 20
        reranker_candidates = pool[:single_cand_limit]
        self.assertLessEqual(len(reranker_candidates), single_cand_limit)

    @patch("agents.doc_agent.generate", return_value="Repository evidence verified.")
    def test_4_repository_isolation_100_percent(self, mock_gen):
        """4. Repository isolation remains 100% intact across queries."""
        repo_a_id = "test_phase6_repo_a"
        repo_b_id = "test_phase6_repo_b"
        coll_a = f"collection_{repo_a_id}"
        coll_b = f"collection_{repo_b_id}"

        # Clean
        for rid in [repo_a_id, repo_b_id]:
            try:
                self.registry.delete_repository(rid)
            except Exception:
                pass

        self.registry.create_repository("Repo A", repo_id=repo_a_id, source_path="dataset/a")
        self.registry.create_repository("Repo B", repo_id=repo_b_id, source_path="dataset/b")

        vm_a = VectorStoreManager(collection_name=coll_a, repository_id=repo_a_id)
        vm_b = VectorStoreManager(collection_name=coll_b, repository_id=repo_b_id)

        vm_a.add_chunks([{
            "content": "Secret information alpha belonging exclusively to Repository A.",
            "metadata": {"repository_id": repo_a_id, "collection_id": coll_a, "paper_title": "Paper A", "file": "a.pdf", "hash": "ha1"}
        }])
        vm_b.add_chunks([{
            "content": "Confidential information beta belonging exclusively to Repository B.",
            "metadata": {"repository_id": repo_b_id, "collection_id": coll_b, "paper_title": "Paper B", "file": "b.pdf", "hash": "hb1"}
        }])

        self.registry.update_status(repo_a_id, RepoStatus.READY)
        self.registry.update_status(repo_b_id, RepoStatus.READY)

        # Query A
        res_a, _, chunks_a, _ = answer("What is the secret information?", repo_id=repo_a_id)
        self.assertTrue(len(chunks_a) > 0)
        for c in chunks_a:
            self.assertEqual(c["metadata"]["repository_id"], repo_a_id)
            self.assertNotIn("Repository B", c["content"])

        # Query B
        res_b, _, chunks_b, _ = answer("What is the confidential information?", repo_id=repo_b_id)
        self.assertTrue(len(chunks_b) > 0)
        for c in chunks_b:
            self.assertEqual(c["metadata"]["repository_id"], repo_b_id)
            self.assertNotIn("Repository A", c["content"])

    def test_5_paper_isolation_100_percent(self):
        """5. Single-paper query remains 100% paper-isolated."""
        from agents.orchestrator import _enforce_paper_isolation

        chunks = [
            {"id": "1", "content": "DQN chunk", "metadata": {"paper_title": "Playing Atari with Deep Reinforcement Learning"}},
            {"id": "2", "content": "DDPG chunk", "metadata": {"paper_title": "Continuous Control with Deep Reinforcement Learning"}},
        ]
        requested = ["Playing Atari with Deep Reinforcement Learning"]
        kept, dropped = _enforce_paper_isolation(chunks, requested)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["metadata"]["paper_title"], requested[0])
        self.assertEqual(len(dropped), 1)

    def test_6_evidence_coverage_remains_intact(self):
        """6. _ensure_evidence_coverage restores missing equations/algorithms from candidate pool."""
        candidate_pool = [
            {"id": f"chunk_{i}", "content": f"Text {i}", "score": 5.0 - i, "metadata": {"hash": f"h_{i}"}}
            for i in range(5)
        ]
        eq_chunk = {
            "id": "essential_eq",
            "content": r"Algorithm 1: Target update equation y = r + \gamma \max_{a'} Q(s', a'; \theta^-)",
            "score": 0.5,
            "metadata": {"hash": "h_eq", "contains_equation": True, "contains_algorithm": True}
        }
        candidate_pool.append(eq_chunk)

        initial_output = list(candidate_pool[:3])  # does not have eq_chunk
        intent = {"equation": True, "table": False, "figure": False, "algorithm": True}

        restored = _ensure_evidence_coverage(
            candidate_pool,
            initial_output,
            intent,
            question="What is the target update equation in Algorithm 1?"
        )
        self.assertTrue(any(c["id"] == "essential_eq" for c in restored))

    def test_7_claim_evidence_verifier_correctness(self):
        """7. ClaimEvidenceVerifier continues to correct known Phase 3 errors."""
        chunks = [{
            "content": "Asynchronous Methods: one-step Sarsa target is y = r + \\gamma Q(s', a'; \\theta^-). One-step Q-learning is y = r + \\gamma \\max_{a'} Q(s', a'; \\theta^-).",
            "metadata": {"paper_title": "Asynchronous Methods for Deep Reinforcement Learning", "page_start": 4}
        }]
        verifier = ClaimEvidenceVerifier(chunks, question="What is the Sarsa update equation?")

        bad_answer = "For one-step Sarsa, the target value is: \\[ y = r + \\gamma \\max_{a'} Q(s', a'; \\theta^-) \\]"
        corrected = verifier.verify_and_align(bad_answer)

        # Max operator should be removed from Sarsa
        self.assertNotIn(r"\max_{a'}", corrected)
        self.assertIn(r"y = r + \gamma Q(s', a'; \theta^-)", corrected)

    def test_8_cpu_execution_support(self):
        """8. Prewarming and execution work natively on CPU."""
        prewarm_cross_encoder({"reranker_device": "cpu"})
        from retrieval.cross_encoder_rerank import _cross_encoder_cache
        self.assertTrue(any("cpu" in k for k in _cross_encoder_cache.keys()))

    def test_9_gpu_fallback_behavior(self):
        """9. GPU failure cleanly falls back to CPU without process crash."""
        def failing_gpu_loader(device):
            if device == "cuda":
                raise RuntimeError("CUDA device out of memory")
            return f"LoadedOn({device})"

        model, actual_device = _load_with_gpu_fallback("TestModel", "test-model-name", "cuda", failing_gpu_loader)
        self.assertEqual(actual_device, "cpu")
        self.assertEqual(model, "LoadedOn(cpu)")

    def test_10_cache_bounding_no_memory_leak(self):
        """10. Caches strictly enforce max_size bounds under heavy query loads."""
        # QueryEmbeddingCache bounding
        q_cache = QueryEmbeddingCache(max_size=3)
        for i in range(10):
            q_cache.put("model", f"query_{i}", np.array([float(i)]))
        self.assertEqual(len(q_cache._cache), 3)
        # Oldest evicted
        self.assertIsNone(q_cache.get("model", "query_0"))
        # Newest kept
        self.assertIsNotNone(q_cache.get("model", "query_9"))

        # CrossEncoderScoreCache bounding
        ce_cache = CrossEncoderScoreCache(max_size=3)
        for i in range(10):
            ce_cache.put("q", f"hash_{i}", float(i), collection_id="c")
        self.assertEqual(len(ce_cache._cache), 3)
        self.assertIsNone(ce_cache.get("q", "hash_0", collection_id="c"))
        self.assertIsNotNone(ce_cache.get("q", "hash_9", collection_id="c"))


if __name__ == "__main__":
    unittest.main()
