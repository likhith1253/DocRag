import unittest

from ingestion.doc_chunker import chunk_document


def _sections(content, heading="Method", page=3):
    return [{
        "heading": heading,
        "page_start": page,
        "page_end": page,
        "content": content,
        "line_pages": [page] * (content.count("\n") + 1),
    }]


class TestEvidenceMetadata(unittest.TestCase):
    """
    Phase 3 Part A: chunks should carry a bounded, honest evidence-type
    signal derived from the same structural heuristics already used for
    chunk_type — never fabricated for content the parser didn't actually
    extract (no image/figure extraction exists — see ingestion/pdf_parser.py).
    """

    def _chunk(self, content):
        chunks = chunk_document(
            file_path="paper.pdf", sections=_sections(content),
            paper_title="T", authors="", year="", collection_id="c1",
        )
        self.assertEqual(len(chunks), 1)
        return chunks[0]["metadata"]

    def test_table_content_flagged(self):
        meta = self._chunk("Results:\n| Method | Score |\n| --- | --- |\n| SAC | 5000 |\nSee Table 2 for details.")
        self.assertTrue(meta["contains_table"])
        self.assertIn("Table 2", meta["table_ids"])
        self.assertFalse(meta["contains_figure"])
        self.assertFalse(meta["contains_algorithm"])

    def test_figure_reference_flagged(self):
        meta = self._chunk("Figure 1 shows the overall architecture of the model and its information flow.")
        self.assertTrue(meta["contains_figure"])
        self.assertIn("Figure 1", meta["figure_ids"])
        self.assertFalse(meta["contains_table"])

    def test_algorithm_reference_flagged(self):
        meta = self._chunk("Algorithm 1 describes the training procedure in detail with numbered steps.")
        self.assertTrue(meta["contains_algorithm"])
        self.assertIn("Algorithm 1", meta["algorithm_ids"])

    def test_plain_prose_has_no_evidence_flags(self):
        meta = self._chunk("This paper introduces a new approach to reinforcement learning that improves sample efficiency.")
        self.assertFalse(meta["contains_table"])
        self.assertFalse(meta["contains_equation"])
        self.assertFalse(meta["contains_figure"])
        self.assertFalse(meta["contains_algorithm"])
        self.assertEqual(meta["table_ids"], [])
        self.assertEqual(meta["figure_ids"], [])
        self.assertEqual(meta["algorithm_ids"], [])

    def test_evidence_type_field_mirrors_chunk_type(self):
        meta = self._chunk("gamma = 0.99\nlearning_rate = 0.001\nbatch_size = 64")
        self.assertEqual(meta["evidence_type"], meta["chunk_type"])

    def test_evidence_flags_never_fabricated_for_absent_content(self):
        # No figure/table/algorithm reference anywhere -> all False, empty ID lists.
        # This is the "do not fabricate metadata" requirement.
        meta = self._chunk("The model was trained for 200 epochs on a single GPU.")
        self.assertFalse(meta["contains_figure"])
        self.assertEqual(meta["figure_ids"], [])

    def test_existing_metadata_preserved_alongside_new_fields(self):
        # Phase 1 fields must still be present and correct.
        meta = self._chunk("Some content.")
        for key in ("collection_id", "document_id", "paper_title", "file", "hash", "section", "page_start"):
            self.assertIn(key, meta)


if __name__ == "__main__":
    unittest.main()
