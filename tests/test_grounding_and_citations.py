"""
Phase 3 Part D/E/G/H lightweight tests. No LLM is invoked — these test the
static prompt text the grounding policy produces (the actual generation
behavior can only be verified with a real model run, which this phase
intentionally does not do) and the citation metadata builder.
"""

import unittest

from agents.doc_agent import (
    _build_context_block,
    _build_adaptive_prompt,
    build_citation_list,
    CANNOT_FIND_RESPONSE,
)


def _chunk(paper_title, text, section="Method", page=3, **evidence_flags):
    meta = {
        "paper_title": paper_title,
        "file": paper_title.replace(" ", "_") + ".pdf",
        "section": section,
        "page_start": page,
        "page_end": page,
        "hash": f"{paper_title}::{text}::{page}",
        "chunk_type": "TEXT",
        "evidence_type": "TEXT",
        "contains_equation": False,
        "contains_table": False,
        "contains_figure": False,
        "contains_algorithm": False,
    }
    meta.update(evidence_flags)
    return {"content": text, "metadata": meta, "score": 1.0, "id": meta["hash"]}


class TestGroundingPolicy(unittest.TestCase):
    """Item 10/11: unsupported numerical/equation claim policy, general grounding."""

    def setUp(self):
        chunks = [_chunk("Soft Actor-Critic", "SAC is an off-policy algorithm.")]
        trace = []
        self.context_block = _build_context_block(chunks, trace)
        self.prompt = _build_adaptive_prompt("What is the objective equation?", self.context_block, "DETAILED", trace)

    def test_prompt_forbids_substituting_remembered_equation(self):
        self.assertIn("do not substitute a remembered", self.prompt.lower())

    def test_prompt_requires_saying_equation_not_found_when_absent(self):
        self.assertIn("say the exact equation was not found", self.prompt.lower())

    def test_prompt_forbids_estimating_missing_numbers(self):
        self.assertIn("not found rather than estimating", self.prompt.lower())

    def test_prompt_addresses_figures_without_claiming_vision(self):
        p = self.prompt.lower()
        self.assertIn("no image was analyzed", p)
        self.assertIn("not available in the retrieved text", p)

    def test_prompt_still_has_canonical_not_found_instruction(self):
        self.assertIn(CANNOT_FIND_RESPONSE, self.prompt)

    def test_prompt_forbids_outside_knowledge(self):
        self.assertIn("zero outside knowledge", self.prompt.lower())

    def test_prompt_is_not_excessively_long(self):
        # Grounding header should stay compact — a bounded number of rules,
        # not an ever-growing policy document.
        header_end = self.prompt.find("=" * 80)
        header = self.prompt[:header_end] if header_end > 0 else self.prompt
        self.assertLess(len(header), 3000)


class TestExcerptEvidenceTags(unittest.TestCase):
    """Item 9/verification: excerpt headers surface evidence type so the
    model can locate the right kind of evidence instead of guessing."""

    def test_equation_chunk_tagged_in_excerpt_header(self):
        chunks = [_chunk("Soft Actor-Critic", "J(pi) = E[R]", contains_equation=True)]
        trace = []
        ctx = _build_context_block(chunks, trace)
        self.assertIn("Evidence: equation", ctx)

    def test_table_and_figure_chunks_tagged(self):
        chunks = [
            _chunk("Soft Actor-Critic", "Table 2 shows results.", section="Results", page=8, contains_table=True),
            _chunk("Soft Actor-Critic", "Figure 1 shows the architecture.", section="Overview", page=1, contains_figure=True),
        ]
        trace = []
        ctx = _build_context_block(chunks, trace)
        self.assertIn("Evidence: table", ctx)
        self.assertIn("Evidence: figure", ctx)

    def test_plain_prose_chunk_has_no_evidence_tag(self):
        chunks = [_chunk("Soft Actor-Critic", "This is plain prose with no special evidence.")]
        trace = []
        ctx = _build_context_block(chunks, trace)
        self.assertNotIn("Evidence:", ctx)


class TestCitationMetadata(unittest.TestCase):
    """Item 12: citation/source metadata preservation and extension."""

    def test_citation_includes_evidence_type_and_chunk_id(self):
        chunks = [_chunk("Soft Actor-Critic", "J(pi) = E[R]", chunk_type="EQUATION", evidence_type="EQUATION", contains_equation=True)]
        citations = build_citation_list(chunks)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0]["evidence_type"], "EQUATION")
        self.assertTrue(citations[0]["chunk_id"])

    def test_existing_citation_fields_unchanged(self):
        chunks = [_chunk("Soft Actor-Critic", "Some text.", section="Method", page=3)]
        citations = build_citation_list(chunks)
        c = citations[0]
        for key in ("paper_title", "authors", "year", "section", "page_start", "page_end", "file", "citation"):
            self.assertIn(key, c)
        self.assertEqual(c["paper_title"], "Soft Actor-Critic")
        self.assertEqual(c["page_start"], 3)
        self.assertIn("[Paper: Soft Actor-Critic", c["citation"])

    def test_citation_traceable_to_page_and_section(self):
        chunks = [_chunk("Soft Actor-Critic", "Some text.", section="Results", page=9)]
        citation = build_citation_list(chunks)[0]
        self.assertIn("Section: Results", citation["citation"])
        self.assertIn("Page 9", citation["citation"])


if __name__ == "__main__":
    unittest.main()
