import unittest

from ingestion.doc_chunker import chunk_document


def _sections(content_a: str, content_b: str = None):
    sections = [
        {
            "heading": "Results",
            "page_start": 5,
            "page_end": 5,
            "content": content_a,
            "line_pages": [5] * (content_a.count("\n") + 1),
        }
    ]
    if content_b is not None:
        sections.append({
            "heading": "Results",
            "page_start": 8,
            "page_end": 8,
            "content": content_b,
            "line_pages": [8] * (content_b.count("\n") + 1),
        })
    return sections


class TestDocChunkerIdentity(unittest.TestCase):
    """
    Regression tests for the indexing-integrity bug where a PDF that repeats
    byte-identical short text at multiple physical locations (e.g. a chart
    axis label reused under several figures) produced chunks whose hash was
    only a function of (content, file_path, collection_id) — so every repeat
    after the first collided onto the same Qdrant point ID and silently
    overwrote the previous one, shrinking the final point count below the
    number of chunks actually generated.
    """

    def test_deterministic_ids_same_input_same_hash(self):
        sections = _sections("The model achieves 92% accuracy on the test set.")
        chunks_1 = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="T", authors="A", year="2024", collection_id="col1",
        )
        chunks_2 = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="T", authors="A", year="2024", collection_id="col1",
        )
        self.assertEqual(len(chunks_1), 1)
        self.assertEqual(
            chunks_1[0]["metadata"]["hash"], chunks_2[0]["metadata"]["hash"]
        )

    def test_different_documents_do_not_collide(self):
        sections = _sections("Identical text repeated verbatim across papers.")
        chunks_a = chunk_document(
            file_path="paper_a.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        chunks_b = chunk_document(
            file_path="paper_b.pdf", sections=sections,
            paper_title="B", authors="", year="", collection_id="col1",
        )
        self.assertNotEqual(chunks_a[0]["metadata"]["hash"], chunks_b[0]["metadata"]["hash"])

    def test_different_collections_do_not_collide(self):
        sections = _sections("Same paper indexed into two isolated collections.")
        chunks_a = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        chunks_b = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col2",
        )
        self.assertNotEqual(chunks_a[0]["metadata"]["hash"], chunks_b[0]["metadata"]["hash"])

    def test_duplicate_content_within_document_gets_distinct_hashes(self):
        """
        Two chunks with byte-identical content at different pages/sections of
        the SAME document must not collapse onto the same hash — each is a
        real, separate chunk and must survive as its own Qdrant point.
        """
        repeated_text = "Training epochs\n0\n10\n20\n30\n40"
        sections = _sections(repeated_text, repeated_text)
        chunks = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        self.assertEqual(len(chunks), 2)
        hashes = [c["metadata"]["hash"] for c in chunks]
        self.assertEqual(len(set(hashes)), 2, "Duplicate in-document chunks must get distinct hashes")
        # The first occurrence keeps its plain content hash unchanged so that
        # re-indexing an existing, already-embedded document doesn't need to
        # re-embed the (much more common) non-duplicated chunks.
        import hashlib
        expected_first = hashlib.sha256(
            (repeated_text + "paper.pdf" + "col1").encode("utf-8")
        ).hexdigest()
        self.assertEqual(hashes[0], expected_first)

    def test_reindexing_duplicate_content_is_stable(self):
        """Running chunk_document twice on a document with in-doc duplicates
        must reproduce the exact same hash sequence (idempotent re-indexing)."""
        repeated_text = "Loss\n0.1\n0.2\n0.3"
        sections = _sections(repeated_text, repeated_text)
        run_1 = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        run_2 = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        self.assertEqual(
            [c["metadata"]["hash"] for c in run_1],
            [c["metadata"]["hash"] for c in run_2],
        )

    def test_document_id_present_and_stable(self):
        sections = _sections("Some content.")
        chunks_1 = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        chunks_2 = chunk_document(
            file_path="paper.pdf", sections=sections,
            paper_title="A", authors="", year="", collection_id="col1",
        )
        self.assertIn("document_id", chunks_1[0]["metadata"])
        self.assertEqual(
            chunks_1[0]["metadata"]["document_id"], chunks_2[0]["metadata"]["document_id"]
        )

    def test_source_metadata_preserved(self):
        sections = _sections("Some content with source metadata.")
        chunks = chunk_document(
            file_path="sub/paper.pdf", sections=sections,
            paper_title="My Paper", authors="A. Author", year="2023",
            collection_id="col1",
        )
        meta = chunks[0]["metadata"]
        self.assertEqual(meta["collection_id"], "col1")
        self.assertEqual(meta["file"], "sub/paper.pdf")
        self.assertEqual(meta["paper_title"], "My Paper")
        self.assertEqual(meta["section"], "Results")
        self.assertEqual(meta["page_start"], 5)
        self.assertIn("hash", meta)


if __name__ == "__main__":
    unittest.main()
