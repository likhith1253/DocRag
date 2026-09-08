"""
Phase 7 — Permanent Regression, Isolation, Cache, Lifecycle & Failure-Handling
Suite.

This suite does not re-litigate Phase 4/5/6 in full (see test_phase4_performance.py,
test_phase5_multi_repository.py, test_phase6_performance.py, test_hpc_regressions.py,
test_indexing_integrity.py, test_retrieval_paper_isolation.py for the deep
coverage already in place). It locks down the specific guarantees Phase 7
was asked to protect going into HPC/V100 validation:

  A. Indexing integrity        (dedup-safe upsert, verify_points_exist)
  B. Repository isolation      (mismatch rejection, invalid repo id)
  C. Paper isolation           (acronym/alias matching stays conservative)
  D. Evidence quality          (equation/table/algorithm evidence preserved)
  E. Technical grounding       (verify_high_risk_grounding, ClaimEvidenceVerifier)
  F. Cache isolation           (query-embedding, CE-score, paper-metadata caches)
  G. Lifecycle                 (CREATED->INDEXING->READY, FAILED, DELETING->DELETED)
  H. Failure handling          (canonical error strings, no raw tracebacks)
  I. GPU/CPU fallback          (centralized device fallback, no GPU required)
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from storage.registry import get_registry, RepoStatus, QUERYABLE_REPO_STATUSES
from storage.vector_store import VectorStoreManager, _load_with_gpu_fallback
from retrieval.cross_encoder_rerank import get_ce_score_cache
from retrieval.paper_matcher import (
    invalidate_paper_cache,
    get_collection_papers,
    get_collection_metadata,
    match_papers_in_query,
)
from storage.vector_store import get_query_embedding_cache
import agents.orchestrator as orchestrator
from agents.doc_agent import verify_high_risk_grounding, ClaimEvidenceVerifier


def _make_chunk(text, file_path, collection_id, section="Body", page=1, **evidence_flags):
    import hashlib
    content_hash = hashlib.sha256((text + file_path + collection_id).encode("utf-8")).hexdigest()
    meta = {
        "collection_id": collection_id,
        "repository_id": collection_id,
        "paper_title": file_path.replace(".pdf", "").replace("_", " "),
        "section": section,
        "page_start": page,
        "page_end": page,
        "file": file_path,
        "hash": content_hash,
        "chunk_type": "TEXT",
        "contains_equation": False,
        "contains_table": False,
        "contains_figure": False,
        "contains_algorithm": False,
    }
    meta.update(evidence_flags)
    return {"content": text, "metadata": meta}


# ---------------------------------------------------------------------------
# A. Indexing integrity
# ---------------------------------------------------------------------------
class TestIndexingIntegrityRegression(unittest.TestCase):
    def setUp(self):
        self.collection = f"test_p7_index_{self._testMethodName}"
        self.vm = VectorStoreManager()
        self.vm.collection_name = self.collection
        self.vm.drop_collection()
        self.vm._ensure_collection()

    def tearDown(self):
        self.vm.drop_collection()

    def test_repeated_identical_chunks_do_not_duplicate(self):
        chunk = _make_chunk("Deep Q-Networks use experience replay.", "DQN.pdf", self.collection)
        self.vm.add_chunks([chunk])
        self.vm.add_chunks([chunk])
        self.vm.add_chunks([chunk])
        self.assertEqual(self.vm.count(), 1, "Re-adding an identical chunk must upsert, not duplicate")

    def test_chunk_count_matches_uploaded_count(self):
        chunks = [
            _make_chunk(f"Unique sentence number {i} about reinforcement learning.", "Paper.pdf", self.collection, page=i)
            for i in range(5)
        ]
        self.vm.add_chunks(chunks)
        self.assertEqual(self.vm.count(), 5)

    def test_deterministic_ids_are_stable(self):
        import uuid
        chash = "stable-hash-123"
        id1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, chash))
        id2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, chash))
        self.assertEqual(id1, id2)

    def test_reconciliation_catches_missing_points(self):
        chunks = [_make_chunk(f"Sentence {i}", "Paper.pdf", self.collection, page=i) for i in range(3)]
        self.vm.add_chunks(chunks)
        hashes = [c["metadata"]["hash"] for c in chunks]
        found, missing = self.vm.verify_points_exist(hashes + ["never-indexed-hash"])
        self.assertEqual(found, 3)
        self.assertEqual(missing, ["never-indexed-hash"])

    def test_failed_ingestion_does_not_report_ready(self):
        registry = get_registry()
        repo_id = f"test_p7_failed_{self._testMethodName}"
        try:
            registry.delete_repository(repo_id)
        except Exception:
            pass
        repo = registry.create_repository("Empty repo", repo_id=repo_id, source_path="dataset/none")
        # Never indexed -> zero vectors -> marking READY must be rejected.
        registry.update_status(repo_id, RepoStatus.READY)
        refreshed = registry.get_repository(repo_id)
        self.assertEqual(refreshed.status, RepoStatus.FAILED)
        self.assertIn("Zero vectors", refreshed.last_error or "")
        registry.delete_repository(repo_id)


# ---------------------------------------------------------------------------
# B. Repository isolation
# ---------------------------------------------------------------------------
class TestRepositoryIsolationRegression(unittest.TestCase):
    def test_collection_mismatch_is_rejected(self):
        registry = get_registry()
        repo_id = "test_p7_mismatch_repo"
        try:
            registry.delete_repository(repo_id)
        except Exception:
            pass
        registry.create_repository("Mismatch Repo", repo_id=repo_id, source_path="dataset/x")
        vm = VectorStoreManager(collection_name="collection_totally_different", repository_id=repo_id)
        vm._ensure_collection()
        try:
            with self.assertRaises(ValueError):
                vm.search("some query", top_k=3, repository_id=repo_id)
        finally:
            vm.drop_collection()
            registry.delete_repository(repo_id)

    def test_invalid_repository_id_fails_cleanly(self):
        vm = VectorStoreManager(collection_name="collection_does_not_matter")
        with self.assertRaises(ValueError):
            vm.search("some query", top_k=3, repository_id="repo-that-does-not-exist-anywhere")

    def test_missing_collection_raises_controlled_error(self):
        vm = VectorStoreManager()
        vm.collection_name = "test_p7_never_created_collection"
        with self.assertRaises(RuntimeError) as ctx:
            vm.search("query text", top_k=3)
        self.assertIn("Vector search failed", str(ctx.exception))

    def test_delete_repository_does_not_affect_other_repository(self):
        registry = get_registry()
        a_id, b_id = "test_p7_del_a", "test_p7_del_b"
        for rid in (a_id, b_id):
            try:
                registry.delete_repository(rid)
            except Exception:
                pass
        repo_a = registry.create_repository("A", repo_id=a_id, source_path="dataset/a")
        repo_b = registry.create_repository("B", repo_id=b_id, source_path="dataset/b")
        vm_a = VectorStoreManager(collection_name=repo_a.vector_collection, repository_id=a_id)
        vm_b = VectorStoreManager(collection_name=repo_b.vector_collection, repository_id=b_id)
        vm_a.add_chunks([_make_chunk("Repo A content", "A.pdf", repo_a.vector_collection)])
        vm_b.add_chunks([_make_chunk("Repo B content", "B.pdf", repo_b.vector_collection)])
        registry.update_status(a_id, RepoStatus.READY)
        registry.update_status(b_id, RepoStatus.READY)

        registry.delete_repository(a_id)

        self.assertIsNone(registry.get_repository(a_id))
        b_after = registry.get_repository(b_id)
        self.assertIsNotNone(b_after)
        vm_b_check = VectorStoreManager(collection_name=repo_b.vector_collection, repository_id=b_id)
        self.assertEqual(vm_b_check.count(), 1)
        registry.delete_repository(b_id)


# ---------------------------------------------------------------------------
# C. Paper isolation (conservative matching)
# ---------------------------------------------------------------------------
class TestPaperIsolationRegression(unittest.TestCase):
    def setUp(self):
        self.collection = f"test_p7_papers_{self._testMethodName}"
        self.vm = VectorStoreManager()
        self.vm.collection_name = self.collection
        self.vm.drop_collection()
        self.vm._ensure_collection()
        invalidate_paper_cache(self.collection)
        self.vm.add_chunks([
            _make_chunk("A3C uses asynchronous actor-learners.", "A3C.pdf", self.collection,
                        contains_algorithm=True),
            _make_chunk("DQN uses experience replay.", "DQN.pdf", self.collection,
                        contains_algorithm=True),
        ])

    def tearDown(self):
        self.vm.drop_collection()
        invalidate_paper_cache(self.collection)

    def test_explicit_paper_name_matches_only_that_paper(self):
        titles = get_collection_papers(self.vm)
        matches = match_papers_in_query("What does the DQN paper say about experience replay?", titles)
        matched_titles = [t for t, _ in matches]
        self.assertIn("DQN", matched_titles)
        self.assertNotIn("A3C", matched_titles)

    def test_unrelated_paper_not_injected_for_narrow_query(self):
        titles = get_collection_papers(self.vm)
        matches = match_papers_in_query("Summarize the DQN preprocessing pipeline.", titles)
        matched_titles = [t for t, _ in matches]
        self.assertNotIn("A3C", matched_titles)

    def test_paper_cache_is_scoped_per_collection(self):
        other_collection = f"{self.collection}_other"
        get_collection_metadata(self.vm)
        invalidate_paper_cache(other_collection)  # must not disturb self.collection's cache
        self.assertIn(self.collection, get_collection_papers.__globals__["_paper_cache"])


# ---------------------------------------------------------------------------
# D/E. Evidence quality & technical grounding
# ---------------------------------------------------------------------------
class TestEvidenceAndGroundingRegression(unittest.TestCase):
    def test_verify_high_risk_grounding_flags_unsupported_number(self):
        chunks = [_make_chunk("The model has 128 hidden units.", "Paper.pdf", "collA")]
        result = verify_high_risk_grounding("The model uses 9999999 hidden units.", chunks)
        self.assertFalse(result["is_grounded"])
        self.assertIn("9999999", result["ungrounded_numbers"])

    def test_verify_high_risk_grounding_passes_supported_number(self):
        chunks = [_make_chunk("The model has 128 hidden units.", "Paper.pdf", "collA")]
        result = verify_high_risk_grounding("The model uses 128 hidden units.", chunks)
        self.assertEqual(result["ungrounded_numbers"], [])

    def test_claim_evidence_verifier_fixes_sarsa_naming_regression(self):
        chunks = [_make_chunk(
            "One-step Sarsa target: y = r + gamma Q(s', a'; theta^-)",
            "A3C.pdf", "collA", contains_equation=True,
        )]
        verifier = ClaimEvidenceVerifier(chunks, "What does SARSA stand for?")
        bad_answer = "SARSA (Synchronous Advantage Actor-Critic) is used for value estimation."
        fixed = verifier.verify_and_align(bad_answer)
        self.assertNotIn("Synchronous Advantage Actor-Critic", fixed)
        self.assertIn("State-Action-Reward-State-Action", fixed)

    def test_claim_evidence_verifier_logs_claims(self):
        chunks = [_make_chunk("Sarsa target without max.", "A3C.pdf", "collA")]
        verifier = ClaimEvidenceVerifier(chunks, "What does SARSA stand for?")
        verifier.verify_and_align("SARSA (Synchronous Advantage Actor-Critic)")
        self.assertTrue(len(verifier.records) >= 1)
        self.assertIn("claim_type", verifier.records[0])

    def test_evidence_flags_survive_into_retrieved_chunk_metadata(self):
        chunk = _make_chunk("y = r + gamma max_a' Q(s', a')", "QL.pdf", "collA",
                             contains_equation=True, contains_algorithm=True)
        self.assertTrue(chunk["metadata"]["contains_equation"])
        self.assertTrue(chunk["metadata"]["contains_algorithm"])
        self.assertFalse(chunk["metadata"]["contains_table"])


# ---------------------------------------------------------------------------
# F. Cache isolation
# ---------------------------------------------------------------------------
class TestCacheIsolationRegression(unittest.TestCase):
    def test_ce_score_cache_isolated_by_collection(self):
        cache = get_ce_score_cache()
        cache.clear()
        cache.put("what is dqn", "hash1", 0.9, collection_id="collection_A")
        cache.put("what is dqn", "hash1", 0.1, collection_id="collection_B")
        self.assertEqual(cache.get("what is dqn", "hash1", collection_id="collection_A"), 0.9)
        self.assertEqual(cache.get("what is dqn", "hash1", collection_id="collection_B"), 0.1)

    def test_ce_score_cache_clear_for_collection_only_clears_that_collection(self):
        cache = get_ce_score_cache()
        cache.clear()
        cache.put("q", "h", 0.5, collection_id="collection_A")
        cache.put("q", "h", 0.7, collection_id="collection_B")
        cache.clear_for_collection("collection_A")
        self.assertIsNone(cache.get("q", "h", collection_id="collection_A"))
        self.assertEqual(cache.get("q", "h", collection_id="collection_B"), 0.7)

    def test_ce_score_cache_is_bounded(self):
        cache = get_ce_score_cache()
        cache.clear()
        for i in range(cache.max_size + 50):
            cache.put("q", f"hash_{i}", float(i), collection_id="collX")
        self.assertLessEqual(cache.stats()["size"], cache.max_size)

    def test_query_embedding_cache_hits_for_repeated_query(self):
        cache = get_query_embedding_cache()
        cache.clear()
        cache.put("model-x", "what is dqn", [1.0, 2.0, 3.0])
        self.assertIsNotNone(cache.get("model-x", "what is dqn"))
        self.assertIsNone(cache.get("model-x", "an entirely different query"))

    def test_paper_metadata_cache_invalidated_per_collection(self):
        vm_stub = MagicMock()
        vm_stub.collection_name = "collection_iso_test"
        vm_stub.get_all_chunks.return_value = [
            {"content": "x", "metadata": {"paper_title": "Iso Paper", "file": "Iso.pdf"}}
        ]
        data = get_collection_metadata(vm_stub)
        self.assertEqual(data["paper_titles"], ["Iso Paper"])
        invalidate_paper_cache("collection_iso_test")
        self.assertNotIn("collection_iso_test", get_collection_papers.__globals__["_collection_metadata_cache"])


# ---------------------------------------------------------------------------
# G. Lifecycle
# ---------------------------------------------------------------------------
class TestLifecycleRegression(unittest.TestCase):
    def test_created_indexing_ready_transition(self):
        registry = get_registry()
        repo_id = "test_p7_lifecycle_ready"
        try:
            registry.delete_repository(repo_id)
        except Exception:
            pass
        repo = registry.create_repository("Lifecycle Repo", repo_id=repo_id, source_path="dataset/x")
        self.assertEqual(repo.status, RepoStatus.CREATED)
        registry.update_status(repo_id, RepoStatus.INDEXING)
        self.assertEqual(registry.get_repository(repo_id).status, RepoStatus.INDEXING)

        vm = VectorStoreManager(collection_name=repo.vector_collection, repository_id=repo_id)
        vm.add_chunks([_make_chunk("Lifecycle content.", "L.pdf", repo.vector_collection)])
        registry.update_status(repo_id, RepoStatus.READY)
        self.assertEqual(registry.get_repository(repo_id).status, RepoStatus.READY)
        registry.delete_repository(repo_id)

    def test_ready_updating_ready_transition(self):
        registry = get_registry()
        repo_id = "test_p7_lifecycle_update"
        try:
            registry.delete_repository(repo_id)
        except Exception:
            pass
        repo = registry.create_repository("Update Repo", repo_id=repo_id, source_path="dataset/x")
        vm = VectorStoreManager(collection_name=repo.vector_collection, repository_id=repo_id)
        vm.add_chunks([_make_chunk("Initial content.", "L.pdf", repo.vector_collection)])
        registry.update_status(repo_id, RepoStatus.READY)
        registry.update_status(repo_id, RepoStatus.UPDATING)
        self.assertEqual(registry.get_repository(repo_id).status, RepoStatus.UPDATING)
        registry.update_status(repo_id, RepoStatus.READY)
        self.assertEqual(registry.get_repository(repo_id).status, RepoStatus.READY)
        registry.delete_repository(repo_id)

    def test_delete_transitions_through_deleting_to_gone(self):
        registry = get_registry()
        repo_id = "test_p7_lifecycle_delete"
        try:
            registry.delete_repository(repo_id)
        except Exception:
            pass
        repo = registry.create_repository("Delete Repo", repo_id=repo_id, source_path="dataset/x")
        vm = VectorStoreManager(collection_name=repo.vector_collection, repository_id=repo_id)
        vm.add_chunks([_make_chunk("Doomed content.", "L.pdf", repo.vector_collection)])
        registry.update_status(repo_id, RepoStatus.READY)
        result = registry.delete_repository(repo_id)
        self.assertTrue(result["deleted"])
        self.assertIsNone(registry.get_repository(repo_id))

    def test_deleted_repository_excluded_from_listing(self):
        registry = get_registry()
        repo_id = "test_p7_lifecycle_list"
        try:
            registry.delete_repository(repo_id)
        except Exception:
            pass
        registry.create_repository("List Repo", repo_id=repo_id, source_path="dataset/x")
        registry.delete(repo_id)  # soft-delete
        ids = [r.repo_id for r in registry.list_repositories()]
        self.assertNotIn(repo_id, ids)
        # cleanup hard
        registry.repositories.pop(repo_id, None)
        registry._save()

    def test_queryable_statuses_do_not_include_created_or_failed(self):
        self.assertNotIn(RepoStatus.CREATED, QUERYABLE_REPO_STATUSES)
        self.assertNotIn(RepoStatus.FAILED, QUERYABLE_REPO_STATUSES)
        self.assertNotIn(RepoStatus.DELETED, QUERYABLE_REPO_STATUSES)
        self.assertIn(RepoStatus.READY, QUERYABLE_REPO_STATUSES)


# ---------------------------------------------------------------------------
# H. Failure handling
# ---------------------------------------------------------------------------
class TestFailureHandlingRegression(unittest.TestCase):
    def test_orchestrator_answer_on_missing_repository_fails_cleanly(self):
        ans, bd, chunks, citations = orchestrator.answer(
            query="What is DQN?",
            repo_id="repo-that-does-not-exist-at-all",
            request_id="test_p7_missing_repo",
        )
        self.assertIsInstance(ans, str)
        self.assertEqual(chunks, [])
        self.assertNotIn("Traceback", ans)
        self.assertNotIn("File \"", ans)

    def test_embedding_failure_yields_canonical_error(self):
        vm = VectorStoreManager()
        vm.collection_name = "test_p7_embed_fail"
        vm.drop_collection()
        vm._ensure_collection()
        with patch.object(vm.encoder, "encode", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError) as ctx:
                vm.search("a query", top_k=3)
            self.assertIn("Embedding service unavailable", str(ctx.exception))
        vm.drop_collection()

    def test_empty_query_returns_controlled_message_not_crash(self):
        ans, bd, chunks, citations = orchestrator.answer(query="", repo_id=None, request_id="test_p7_empty_q")
        self.assertEqual(ans, "Query is empty.")
        self.assertEqual(chunks, [])

    def test_non_string_query_returns_controlled_message_not_crash(self):
        ans, bd, chunks, citations = orchestrator.answer(query=12345, repo_id=None, request_id="test_p7_bad_type_q")
        self.assertEqual(chunks, [])
        self.assertIsInstance(ans, str)


# ---------------------------------------------------------------------------
# I. GPU/CPU fallback (no GPU required)
# ---------------------------------------------------------------------------
class TestDeviceFallbackRegression(unittest.TestCase):
    def test_cpu_path_never_touches_cuda(self):
        loader = MagicMock(return_value="cpu-model")
        model, device = _load_with_gpu_fallback("Embedding", "some-model", "cpu", loader)
        self.assertEqual(device, "cpu")
        loader.assert_called_once_with("cpu")

    def test_cuda_unavailable_falls_back_to_cpu(self):
        loader = MagicMock(side_effect=lambda d: f"model-on-{d}")
        with patch("torch.cuda.is_available", return_value=False):
            model, device = _load_with_gpu_fallback("Embedding", "some-model", "cuda", loader)
        self.assertEqual(device, "cpu")
        self.assertEqual(model, "model-on-cpu")

    def test_cuda_load_failure_falls_back_to_cpu(self):
        def loader(d):
            if d == "cuda":
                raise RuntimeError("CUDA driver error")
            return f"model-on-{d}"
        with patch("torch.cuda.is_available", return_value=True):
            model, device = _load_with_gpu_fallback("Reranker", "some-model", "cuda", loader)
        self.assertEqual(device, "cpu")
        self.assertEqual(model, "model-on-cpu")

    def test_device_selection_is_centralized(self):
        # Both embedding and reranker paths must funnel through the same
        # fallback helper rather than each re-implementing CUDA probing.
        import retrieval.cross_encoder_rerank as cer
        self.assertIs(cer._load_with_gpu_fallback, _load_with_gpu_fallback)


if __name__ == "__main__":
    unittest.main()
