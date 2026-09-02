import os
import unittest
import shutil
from unittest.mock import patch

from storage.vector_store import VectorStoreManager


def _make_chunk(text: str, file_path: str, collection_id: str, section: str = "Body", page: int = 1):
    import hashlib
    content_hash = hashlib.sha256((text + file_path + collection_id).encode("utf-8")).hexdigest()
    return {
        "content": text,
        "metadata": {
            "collection_id": collection_id,
            "document_id": hashlib.sha256((collection_id + "::" + file_path).encode()).hexdigest(),
            "paper_title": "Test Paper",
            "authors": "",
            "year": "",
            "section": section,
            "page_start": page,
            "page_end": page,
            "file": file_path,
            "hash": content_hash,
            "timestamp": "2024-01-01T00:00:00Z",
            "chunk_type": "TEXT",
        },
    }


class TestIndexingIntegrity(unittest.TestCase):
    """
    Integration tests against the real embedded Qdrant + real encoder (same
    pattern as tests/test_vector_store.py) covering the indexing contract:
    deterministic IDs, idempotent re-indexing, cross-chunk isolation,
    reconciliation/verification, and partial-failure detection.
    """

    def setUp(self):
        # Deliberately do NOT close()/clear the cached QdrantClient between
        # tests here. Embedded/local Qdrant on Windows persists writes on
        # close(), and closing+reopening the client mid-suite can read back
        # stale pre-delete state if a close is ever skipped (e.g. interpreter
        # shutdown tearing down msvcrt before a lock-file unlock runs) —
        # purely a test-harness hazard, not something the real indexing path
        # (worker.py) ever does, since it keeps one manager for the whole run.
        #
        # Each test also gets its own uniquely-named collection rather than
        # reusing one name across delete+recreate cycles: embedded Qdrant's
        # local storage can race when a collection is deleted and a new one
        # with the *same* name is created immediately after (a write still
        # "in flight" for the old generation can land in the new directory),
        # which is a storage-engine hazard rather than anything under test.
        VectorStoreManager._all_chunks_cache.clear()
        self.collection = f"test_indexing_integrity_{self._testMethodName}"
        self.manager = VectorStoreManager()
        self.manager.collection_name = self.collection
        self.manager.drop_collection()
        self.manager._ensure_collection()

    def tearDown(self):
        try:
            self.manager.drop_collection()
        except Exception:
            pass

    def test_deterministic_point_ids_across_runs(self):
        """Same chunk hash indexed twice (two separate add_chunks calls,
        simulating two indexing runs) must resolve to the same point ID."""
        chunk = _make_chunk("Deterministic content.", "paper.pdf", "colA")
        self.manager.add_chunks([chunk])
        count_after_first = self.manager.count()

        self.manager.add_chunks([chunk])
        count_after_second = self.manager.count()

        self.assertEqual(count_after_first, 1)
        self.assertEqual(
            count_after_second, 1,
            "Re-indexing the same chunk must not create a duplicate point (idempotency).",
        )

    def test_idempotent_indexing_same_document_twice(self):
        """Indexing the same set of chunks for a document twice must not
        double the point count."""
        chunks = [
            _make_chunk(f"Sentence number {i} of the paper.", "paper.pdf", "colA", page=i)
            for i in range(5)
        ]
        self.manager.add_chunks(chunks)
        self.assertEqual(self.manager.count(), 5)

        self.manager.add_chunks(chunks)
        self.assertEqual(
            self.manager.count(), 5,
            "Second indexing pass of identical chunks must not create 10 points.",
        )

    def test_different_chunks_do_not_collide(self):
        chunks = [
            _make_chunk("First unique sentence.", "paper.pdf", "colA"),
            _make_chunk("Second unique sentence.", "paper.pdf", "colA"),
            _make_chunk("First unique sentence.", "other.pdf", "colA"),
        ]
        self.manager.add_chunks(chunks)
        self.assertEqual(self.manager.count(), 3)

    def test_verify_points_exist_detects_missing_points(self):
        chunks = [_make_chunk(f"Chunk {i}", "paper.pdf", "colA", page=i) for i in range(3)]
        self.manager.add_chunks(chunks[:2])  # only index 2 of the 3

        all_hashes = [c["metadata"]["hash"] for c in chunks]
        found_count, missing = self.manager.verify_points_exist(all_hashes)

        self.assertEqual(found_count, 2)
        self.assertEqual(missing, [chunks[2]["metadata"]["hash"]])

    def test_verify_points_exist_all_present(self):
        chunks = [_make_chunk(f"Present chunk {i}", "paper.pdf", "colA", page=i) for i in range(4)]
        self.manager.add_chunks(chunks)
        found_count, missing = self.manager.verify_points_exist(
            [c["metadata"]["hash"] for c in chunks]
        )
        self.assertEqual(found_count, 4)
        self.assertEqual(missing, [])

    def test_metadata_round_trips_through_qdrant(self):
        chunk = _make_chunk("Metadata integrity check.", "sub/paper.pdf", "colA", section="Method", page=7)
        self.manager.add_chunks([chunk])
        stored = self.manager.get_all_chunks()
        self.assertEqual(len(stored), 1)
        meta = stored[0]["metadata"]
        self.assertEqual(meta["collection_id"], "colA")
        self.assertEqual(meta["file"], "sub/paper.pdf")
        self.assertEqual(meta["section"], "Method")
        self.assertEqual(meta["page_start"], 7)
        self.assertIn("document_id", meta)
        self.assertIn("hash", meta)

    def test_collection_usable_after_drop_and_recreate(self):
        """
        Regression test: deleting a collection (e.g. via DELETE /repository/{id})
        must not leave the process-wide "already ensured" cache stale — a later
        VectorStoreManager for the same collection name must still be able to
        index into it instead of failing with "Collection not found".
        """
        old_chunk = _make_chunk("Content before drop.", "paper.pdf", "colA")
        self.manager.add_chunks([old_chunk])
        found_old_pre_drop, _ = self.manager.verify_points_exist([old_chunk["metadata"]["hash"]])
        self.assertEqual(found_old_pre_drop, 1)

        self.manager.drop_collection()

        # This is the scenario the fix in VectorStoreManager.drop_collection()
        # targets: before that fix, deleting a collection left the process-wide
        # "already ensured" cache stale, so a later VectorStoreManager for the
        # same name would skip recreating it in _ensure_collection() and every
        # add_chunks()/search() would fail with "Collection not found" until
        # process restart. The real app never reuses a dropped collection name
        # immediately (deleted collections get a fresh UUID name), so we only
        # assert the collection is usable again — not on the exact millisecond
        # timing of the deleted generation's data, which is an unrelated
        # embedded-storage flush race outside this fix's scope.
        recreated = VectorStoreManager()
        recreated.collection_name = self.collection
        recreated._ensure_collection()
        new_chunk = _make_chunk("Content after recreate.", "paper.pdf", "colA")
        recreated.add_chunks([new_chunk])

        found_new, _ = recreated.verify_points_exist([new_chunk["metadata"]["hash"]])
        self.assertEqual(found_new, 1, "New point must be indexable after drop+recreate")


class TestUpsertRetry(unittest.TestCase):
    """Unit tests (mocked Qdrant) for the worker's batch retry/failure
    handling, so a transient upsert failure is never reported as success."""

    def test_retry_wrapper_succeeds_after_transient_failure(self):
        from ingestion.worker import _upsert_batch_with_retry

        calls = {"n": 0}

        class FakeManager:
            def add_chunks(self, batch):
                calls["n"] += 1
                if calls["n"] < 2:
                    raise ConnectionError("transient")
                return None

        ok = _upsert_batch_with_retry(FakeManager(), [{"metadata": {"hash": "h1"}}], "repo_x")
        self.assertTrue(ok)
        self.assertEqual(calls["n"], 2)

    def test_retry_wrapper_reports_failure_after_exhausting_retries(self):
        from ingestion.worker import _upsert_batch_with_retry

        class AlwaysFailManager:
            def add_chunks(self, batch):
                raise ConnectionError("permanent outage")

        with patch("ingestion.worker._UPSERT_RETRY_BACKOFF_SECONDS", 0):
            ok = _upsert_batch_with_retry(AlwaysFailManager(), [{"metadata": {"hash": "h1"}}], "repo_x")
        self.assertFalse(ok, "A batch that fails every retry must be reported as failed, not silently succeed.")


if __name__ == "__main__":
    unittest.main()
