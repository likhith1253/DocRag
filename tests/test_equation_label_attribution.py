"""Generic equation-label attribution and excerpt-boundary regression tests."""

import unittest

from agents.doc_agent import _build_context_block, _build_adaptive_prompt, _extract_equation_labels


def _chunk(title, text, section="Method", page=3, **evidence_flags):
    metadata = {
        "paper_title": title,
        "file": title.replace(" ", "_") + ".pdf",
        "section": section,
        "page_start": page,
        "page_end": page,
        "hash": f"{title}::{text}::{page}",
        "chunk_type": "TEXT",
        "evidence_type": "TEXT",
        "contains_equation": False,
        "contains_table": False,
        "contains_figure": False,
        "contains_algorithm": False,
    }
    metadata.update(evidence_flags)
    return {"content": text, "metadata": metadata, "score": 1.0, "id": metadata["hash"]}


EQUATION_A = "Method Alpha: z = x + beta * y"
EQUATION_B = "Method Beta: z = x - beta * y"


class TestEquationLabelExtraction(unittest.TestCase):
    def test_extracts_labels_from_source_text(self):
        self.assertIn("Method Alpha", _extract_equation_labels(EQUATION_A))
        self.assertIn("Method Beta", _extract_equation_labels(EQUATION_B))

    def test_does_not_invent_a_label_for_unlabeled_equation(self):
        self.assertEqual(_extract_equation_labels("z = x + beta * y"), [])

    def test_plain_prose_has_no_labels(self):
        self.assertEqual(_extract_equation_labels("This procedure uses a bounded memory buffer."), [])


class TestAdjacentEquationExcerptSeparation(unittest.TestCase):
    def setUp(self):
        chunks = [
            _chunk("Synthetic Study", EQUATION_A, section="Methods", page=4, contains_equation=True),
            _chunk("Synthetic Study", EQUATION_B, section="Methods", page=5, contains_equation=True),
        ]
        self.context = _build_context_block(chunks, [])

    def test_each_equation_has_its_own_excerpt(self):
        self.assertEqual(self.context.count("[EXCERPT "), 2)

    def test_labels_remain_attached_to_their_source_equation(self):
        excerpts = self.context.split("[EXCERPT ")[1:]
        self.assertEqual(len(excerpts), 2)
        self.assertIn("Equation labels: Method Alpha", excerpts[0])
        self.assertIn("Equation labels: Method Beta", excerpts[1])
        self.assertNotIn(EQUATION_B, excerpts[0])
        self.assertNotIn(EQUATION_A, excerpts[1])

    def test_prompt_preserves_source_labels_without_topic_rules(self):
        prompt = _build_adaptive_prompt("Compare the two update rules.", self.context, "COMPARATIVE", [])
        self.assertIn("Preserve labels that the source places next to methods or equations", prompt)
        self.assertIn("Equation labels: Method Alpha", prompt)
        self.assertIn("Equation labels: Method Beta", prompt)
        self.assertNotIn("Q-learning", prompt)


if __name__ == "__main__":
    unittest.main()
