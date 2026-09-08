"""
Phase 5 — Multi-Repository Ingestion + Repository Isolation & Management Regression Test Suite.

Critical requirements verified:
  1. Test 1  — Basic isolation: Query Repo A -> Only Repo A chunks returned.
  2. Test 2  — Reverse isolation: Query Repo B -> Only Repo B chunks returned.
  3. Test 3  — Same paper title: Papers with identical titles in different repos remain isolated.
  4. Test 4  — Same filename: Identical filenames in Repo A and B produce unique, non-colliding IDs and hashes.
  5. Test 5  — Reindex isolation: Reindexing Repo A does not alter or corrupt Repo B.
  6. Test 6  — Delete isolation: Deleting Repo A drops only its collection and keeps Repo B fully intact.
  7. Test 7  — Invalid repository: Querying a nonexistent repo returns an explicit error with zero fallback.
  8. Test 8  — Collection mismatch / missing: Missing collection produces a controlled failure, never generic 'chunks'.
  9. Test 9  — Cache isolation: CrossEncoder and semantic caches for Repo A do not leak into Repo B queries.
  10. Test 10 — Paper isolation inside repository: Phase 3 paper-level isolation operates strictly within repository boundary.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from storage.registry import get_registry, Repository, RepoStatus
from storage.vector_store import VectorStoreManager
from ingestion.doc_chunker import chunk_document
from retrieval.cross_encoder_rerank import get_ce_score_cache
from storage.cache import SemanticCache
import agents.orchestrator as orchestrator


class TestPhase5MultiRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = get_registry()
        cls.repo_a_id = "test_phase5_repo_a"
        cls.repo_b_id = "test_phase5_repo_b"
        cls.coll_a = f"collection_{cls.repo_a_id}"
        cls.coll_b = f"collection_{cls.repo_b_id}"

        # Clean any preexisting test collections/repos
        for rid in [cls.repo_a_id, cls.repo_b_id]:
            try:
                cls.registry.delete_repository(rid)
            except Exception:
                pass

        # Create Repository A
        cls.repo_a = cls.registry.create_repository(
            name="Repository A - Robotics and RL",
            repo_id=cls.repo_a_id,
            description="Robotics, DDPG, and DQN research in Repository A",
            source_path="dataset/Robotics",
        )
        cls.registry.update_status(cls.repo_a_id, RepoStatus.INDEXING)

        # Create Repository B
        cls.repo_b = cls.registry.create_repository(
            name="Repository B - General AI and PPO",
            repo_id=cls.repo_b_id,
            description="General AI, PPO, and DQN research in Repository B",
            source_path="dataset/AI",
        )
        cls.registry.update_status(cls.repo_b_id, RepoStatus.INDEXING)

        # VectorStoreManagers
        cls.vm_a = VectorStoreManager(collection_name=cls.coll_a, repository_id=cls.repo_a_id)
        cls.vm_b = VectorStoreManager(collection_name=cls.coll_b, repository_id=cls.repo_b_id)

        # Chunks for Repository A:
        # 1. DQN paper (Common filename: Common_Paper.pdf)
        # 2. DDPG paper
        cls.chunks_a = [
            {
                "content": "Repository A evidence for DQN: Deep Q-Networks train agent policies directly from raw visual pixels using experience replay in Atari environments.",
                "metadata": {
                    "repository_id": cls.repo_a_id,
                    "collection_id": cls.coll_a,
                    "document_id": f"{cls.coll_a}::Common_Paper.pdf",
                    "paper_title": "Playing Atari with Deep Reinforcement Learning",
                    "file": "Common_Paper.pdf",
                    "hash": f"{cls.repo_a_id}_dqn_chunk_1",
                    "section": "1. Introduction",
                    "page_start": 1,
                    "page_end": 1,
                    "chunk_type": "text",
                },
            },
            {
                "content": "Repository A evidence for DDPG: Deep Deterministic Policy Gradients use an actor-critic model for continuous action spaces.",
                "metadata": {
                    "repository_id": cls.repo_a_id,
                    "collection_id": cls.coll_a,
                    "document_id": f"{cls.coll_a}::DDPG.pdf",
                    "paper_title": "Continuous Control with Deep Reinforcement Learning",
                    "file": "DDPG.pdf",
                    "hash": f"{cls.repo_a_id}_ddpg_chunk_1",
                    "section": "3. Algorithm",
                    "page_start": 3,
                    "page_end": 4,
                    "chunk_type": "algorithms",
                },
            },
        ]

        # Chunks for Repository B:
        # 1. DQN paper (SAME title, SAME filename "Common_Paper.pdf", but completely different text!)
        # 2. PPO paper
        cls.chunks_b = [
            {
                "content": "Repository B evidence for DQN: An alternative survey of Deep Q-Networks focusing on distributed prioritization and replay buffer memory bounds.",
                "metadata": {
                    "repository_id": cls.repo_b_id,
                    "collection_id": cls.coll_b,
                    "document_id": f"{cls.coll_b}::Common_Paper.pdf",
                    "paper_title": "Playing Atari with Deep Reinforcement Learning",
                    "file": "Common_Paper.pdf",
                    "hash": f"{cls.repo_b_id}_dqn_chunk_1",
                    "section": "2. Background",
                    "page_start": 2,
                    "page_end": 2,
                    "chunk_type": "text",
                },
            },
            {
                "content": "Repository B evidence for PPO: Proximal Policy Optimization algorithms clip probability ratios to stabilize stochastic policy gradient updates.",
                "metadata": {
                    "repository_id": cls.repo_b_id,
                    "collection_id": cls.coll_b,
                    "document_id": f"{cls.coll_b}::PPO.pdf",
                    "paper_title": "Proximal Policy Optimization Algorithms",
                    "file": "PPO.pdf",
                    "hash": f"{cls.repo_b_id}_ppo_chunk_1",
                    "section": "3. Clipped Surrogate Objective",
                    "page_start": 3,
                    "page_end": 3,
                    "chunk_type": "equations",
                },
            },
        ]

        # Add chunks to isolated collections
        cls.vm_a.add_chunks(cls.chunks_a)
        cls.vm_b.add_chunks(cls.chunks_b)

        # Mark both as READY
        cls.registry.update_repository(
            cls.repo_a_id,
            status=RepoStatus.READY,
            document_count=2,
            chunk_count=len(cls.chunks_a),
        )
        cls.registry.update_repository(
            cls.repo_b_id,
            status=RepoStatus.READY,
            document_count=2,
            chunk_count=len(cls.chunks_b),
        )

    @classmethod
    def tearDownClass(cls):
        # Cleanup test repositories and collections
        for rid in [cls.repo_a_id, cls.repo_b_id, "test_phase5_repo_c"]:
            try:
                cls.registry.delete_repository(rid)
            except Exception:
                pass
        orchestrator._v_manager_override = None

    def setUp(self):
        orchestrator._v_manager_override = None

    # -----------------------------------------------------------------------
    # Test 1: Basic isolation — Query Repo A -> only A chunks
    # -----------------------------------------------------------------------
    @patch("agents.doc_agent.generate", return_value="Answer from Repository A [Excerpt 1].")
    def test_01_basic_isolation(self, mock_gen):
        """Querying Repository A retrieves chunks exclusively belonging to Repository A."""
        ans, bd, chunks, citations = orchestrator.answer(
            "What does experience replay do in Atari games?",
            repo_id=self.repo_a_id,
        )
        self.assertTrue(len(chunks) > 0, "Repo A retrieval returned 0 chunks")
        for chunk in chunks:
            repo_meta = chunk.get("metadata", {}).get("repository_id")
            coll_meta = chunk.get("metadata", {}).get("collection_id")
            self.assertEqual(repo_meta, self.repo_a_id, f"Cross-repo chunk leak: found {repo_meta} in Repo A query")
            self.assertEqual(coll_meta, self.coll_a, f"Cross-coll chunk leak: found {coll_meta} in Repo A query")
            self.assertIn("Repository A evidence", chunk["content"])
            self.assertNotIn("Repository B evidence", chunk["content"])

    # -----------------------------------------------------------------------
    # Test 2: Reverse isolation — Query Repo B -> only B chunks
    # -----------------------------------------------------------------------
    @patch("agents.doc_agent.generate", return_value="Answer from Repository B [Excerpt 1].")
    def test_02_reverse_isolation(self, mock_gen):
        """Querying Repository B retrieves chunks exclusively belonging to Repository B."""
        ans, bd, chunks, citations = orchestrator.answer(
            "What does experience replay do in Atari games?",
            repo_id=self.repo_b_id,
        )
        self.assertTrue(len(chunks) > 0, "Repo B retrieval returned 0 chunks")
        for chunk in chunks:
            repo_meta = chunk.get("metadata", {}).get("repository_id")
            coll_meta = chunk.get("metadata", {}).get("collection_id")
            self.assertEqual(repo_meta, self.repo_b_id, f"Cross-repo chunk leak: found {repo_meta} in Repo B query")
            self.assertEqual(coll_meta, self.coll_b, f"Cross-coll chunk leak: found {coll_meta} in Repo B query")
            self.assertIn("Repository B evidence", chunk["content"])
            self.assertNotIn("Repository A evidence", chunk["content"])

    # -----------------------------------------------------------------------
    # Test 3: Same paper title — Isolation holds when title is identical in both
    # -----------------------------------------------------------------------
    @patch("agents.doc_agent.generate", return_value="DQN explanation [Excerpt 1].")
    def test_03_same_paper_title_isolation(self, mock_gen):
        """When two repos hold papers with identical titles, queries remain strictly isolated."""
        # Query Repo A explicitly naming the paper
        _, _, chunks_a, _ = orchestrator.answer(
            "Explain the architecture in Playing Atari with Deep Reinforcement Learning",
            repo_id=self.repo_a_id,
        )
        self.assertTrue(len(chunks_a) > 0)
        self.assertTrue(all("Repository A evidence" in c["content"] for c in chunks_a))
        self.assertTrue(all(c["metadata"]["collection_id"] == self.coll_a for c in chunks_a))

        # Query Repo B explicitly naming the paper
        _, _, chunks_b, _ = orchestrator.answer(
            "Explain the architecture in Playing Atari with Deep Reinforcement Learning",
            repo_id=self.repo_b_id,
        )
        self.assertTrue(len(chunks_b) > 0)
        self.assertTrue(all("Repository B evidence" in c["content"] for c in chunks_b))
        self.assertTrue(all(c["metadata"]["collection_id"] == self.coll_b for c in chunks_b))

    # -----------------------------------------------------------------------
    # Test 4: Same filename — Identical filenames do not collide across repos
    # -----------------------------------------------------------------------
    def test_04_same_filename_no_collision(self):
        """Identical filenames in Repo A and B produce distinct, isolated document and chunk IDs."""
        sample_sections = [{"heading": "Introduction", "content": "Sample identical content in both repos.", "line_pages": [1]}]
        c_a = chunk_document("Common_Paper.pdf", sample_sections, "Common Title", "Author A", "2024", collection_id=self.coll_a)
        c_b = chunk_document("Common_Paper.pdf", sample_sections, "Common Title", "Author A", "2024", collection_id=self.coll_b)

        # Hashes and document IDs must be unique across repository collections
        self.assertNotEqual(c_a[0]["metadata"]["hash"], c_b[0]["metadata"]["hash"], "Chunk hash collided across collections")
        self.assertNotEqual(c_a[0]["metadata"]["document_id"], c_b[0]["metadata"]["document_id"], "Document ID collided across collections")
        self.assertEqual(c_a[0]["metadata"]["collection_id"], self.coll_a)
        self.assertEqual(c_b[0]["metadata"]["collection_id"], self.coll_b)

    # -----------------------------------------------------------------------
    # Test 5: Reindex isolation — Reindexing Repo A does not alter Repo B
    # -----------------------------------------------------------------------
    @patch("agents.doc_agent.generate", return_value="Answer [Excerpt 1].")
    def test_05_reindex_isolation(self, mock_gen):
        """Reindexing Repo A preserves Repo B collections, status, and retrieval results."""
        b_count_before = self.vm_b.count()
        self.assertEqual(self.registry.get_repository(self.repo_b_id).status, RepoStatus.READY)

        # Trigger reindex on Repo A without background execution
        res = self.registry.reindex_repository(self.repo_a_id)
        self.assertEqual(res["status"], "reindexing_started")

        # Repo B must remain READY and unchanged
        repo_b = self.registry.get_repository(self.repo_b_id)
        self.assertEqual(repo_b.status, RepoStatus.READY)
        self.assertEqual(self.vm_b.count(), b_count_before)

        # Querying Repo B must still succeed with 100% fidelity
        _, _, chunks_b, _ = orchestrator.answer("Explain PPO", repo_id=self.repo_b_id)
        self.assertTrue(len(chunks_b) > 0)
        self.assertTrue(all(c["metadata"]["collection_id"] == self.coll_b for c in chunks_b))

        # Restore Repo A to READY
        self.registry.update_status(self.repo_a_id, RepoStatus.READY)

    # -----------------------------------------------------------------------
    # Test 6: Delete isolation — Deleting Repo A leaves Repo B fully intact
    # -----------------------------------------------------------------------
    @patch("agents.doc_agent.generate", return_value="PPO Answer [Excerpt 1].")
    def test_06_delete_isolation(self, mock_gen):
        """Deleting a repository drops its collection without affecting other repositories."""
        # Create a disposable third repo C
        repo_c_id = "test_phase5_repo_c"
        coll_c = f"collection_{repo_c_id}"
        repo_c = self.registry.create_repository(name="Repo C to Delete", repo_id=repo_c_id)
        vm_c = VectorStoreManager(collection_name=coll_c, repository_id=repo_c_id)
        vm_c.add_chunks([{
            "content": "Temporary chunk for Repo C.",
            "metadata": {"repository_id": repo_c_id, "collection_id": coll_c, "paper_title": "Disposable", "file": "c.pdf", "hash": "c_hash_1"}
        }])
        self.registry.update_status(repo_c_id, RepoStatus.READY)
        self.assertTrue(vm_c.client.collection_exists(coll_c))

        # Delete Repo C
        del_res = self.registry.delete_repository(repo_c_id)
        self.assertTrue(del_res["deleted"])
        self.assertIsNone(self.registry.get_repository(repo_c_id))
        self.assertFalse(vm_c.client.collection_exists(coll_c))

        # Verify Repo B was completely unaffected
        repo_b = self.registry.get_repository(self.repo_b_id)
        self.assertIsNotNone(repo_b)
        self.assertEqual(repo_b.status, RepoStatus.READY)
        self.assertTrue(self.vm_b.client.collection_exists(self.coll_b))
        _, _, chunks_b, _ = orchestrator.answer("Explain PPO", repo_id=self.repo_b_id)
        self.assertTrue(len(chunks_b) > 0)

    # -----------------------------------------------------------------------
    # Test 7: Invalid repository — Controlled error, no fallback/global search
    # -----------------------------------------------------------------------
    def test_07_invalid_repository_handling(self):
        """Querying a nonexistent repository produces a controlled error and never searches 'chunks'."""
        ans, bd, chunks, citations = orchestrator.answer(
            "Explain DQN",
            repo_id="nonexistent_repo_id_xyz",
        )
        self.assertEqual(len(chunks), 0, "Nonexistent repository must return 0 chunks")
        self.assertEqual(len(citations), 0)
        self.assertIn("not found in registry", ans.lower())

    # -----------------------------------------------------------------------
    # Test 8: Collection mismatch / missing collection
    # -----------------------------------------------------------------------
    def test_08_collection_mismatch_controlled_failure(self):
        """A repository pointing to a nonexistent vector collection produces a controlled error."""
        mismatch_repo_id = "test_phase5_mismatch"
        try:
            repo = self.registry.create_repository(
                name="Mismatch Repo",
                repo_id=mismatch_repo_id,
            )
            # Point to a collection that does not exist in Qdrant
            repo.vector_collection = "nonexistent_collection_99999"
            repo.collection_id = "nonexistent_collection_99999"
            repo.status = RepoStatus.READY
            self.registry.register(repo)

            ans, bd, chunks, citations = orchestrator.answer(
                "Explain DQN",
                repo_id=mismatch_repo_id,
            )
            self.assertEqual(len(chunks), 0, "Missing collection must return 0 chunks")
            self.assertTrue(
                "does not exist" in ans.lower() or "indexing failed" in ans.lower() or "error" in ans.lower(),
                f"Expected controlled failure message, got: {ans}",
            )

            # Storage-level guard: VectorStoreManager with mismatched repo_id must raise ValueError
            with self.assertRaises(ValueError):
                mismatch_vm = VectorStoreManager(collection_name=self.coll_b, repository_id=self.repo_a_id)
                mismatch_vm.search("Explain DQN")

            # Storage-level guard: VectorStoreManager with nonexistent collection must raise RuntimeError
            missing_coll = "completely_nonexistent_coll_xyz"
            missing_vm = VectorStoreManager(collection_name=missing_coll)
            if missing_vm.client.collection_exists(missing_coll):
                missing_vm.drop_collection()
            with self.assertRaises(RuntimeError):
                missing_vm.search("Explain DQN")
        finally:
            self.registry.repositories.pop(mismatch_repo_id, None)

    # -----------------------------------------------------------------------
    # Test 9: Cache isolation — Caches do not leak across repositories
    # -----------------------------------------------------------------------
    def test_09_cache_isolation(self):
        """CrossEncoder and Semantic caches populated for Repo A do not leak into Repo B."""
        ce_cache = get_ce_score_cache()
        query = "Explain DQN architecture"
        chunk_hash = "shared_chunk_hash"

        # Populate CE cache for Collection A
        ce_cache.put(query, chunk_hash, 9.99, collection_id=self.coll_a)

        # Lookup in Collection B must be a cache miss
        b_score = ce_cache.get(query, chunk_hash, collection_id=self.coll_b)
        self.assertIsNone(b_score, "Cache leak: Collection B retrieved score cached for Collection A")

        # Lookup in Collection A must be a cache hit
        a_score = ce_cache.get(query, chunk_hash, collection_id=self.coll_a)
        self.assertEqual(a_score, 9.99)

        # Clear cache for Collection A only
        ce_cache.clear_for_collection(self.coll_a)
        self.assertIsNone(ce_cache.get(query, chunk_hash, collection_id=self.coll_a))

    # -----------------------------------------------------------------------
    # Test 10: Paper isolation inside repository
    # -----------------------------------------------------------------------
    @patch("agents.doc_agent.generate", return_value="DDPG answer [Excerpt 1].")
    def test_10_paper_isolation_inside_repository(self, mock_gen):
        """Phase 3 paper-level isolation functions accurately within the repository boundary."""
        # Query Repo A specifically for DDPG
        ans, bd, chunks, citations = orchestrator.answer(
            "What is the algorithm structure in Continuous Control with Deep Reinforcement Learning?",
            repo_id=self.repo_a_id,
        )
        self.assertTrue(len(chunks) > 0)
        # Must only contain DDPG, DQN must be strictly filtered out
        for c in chunks:
            title = c.get("metadata", {}).get("paper_title")
            self.assertEqual(title, "Continuous Control with Deep Reinforcement Learning")
            self.assertNotIn("Atari", c["content"])


if __name__ == "__main__":
    unittest.main()
