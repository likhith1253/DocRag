"""
Regression tests for the A3C Q-learning-vs-Sarsa grounding failure (Phase 3
Test 1): retrieval surfaced both targets correctly, but generation still gave
the same target for both. Root cause: two independently-flagged equation
chunks (Q-learning target on one page, Sarsa target on the next) were merged
into a single excerpt with no boundary and no per-equation attribution, which
made it easy for the model to conflate the two.

These tests cover the two structural fixes in agents/doc_agent.py:
  1. Two adjacent equation-bearing chunks are never merged into one excerpt.
  2. A generic (non-hardcoded) per-equation label is extracted from the
     source text and surfaced in the excerpt header, and the grounding
     prompt requires the model to respect that label.
"""

import unittest

from agents.doc_agent import (
    _build_context_block,
    _build_adaptive_prompt,
    _extract_equation_labels,
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


QLEARNING_TEXT = "Q-learning: r + gamma * max_a' Q(s', a')"
SARSA_TEXT = "Sarsa: r + gamma * Q(s', a')"


class TestEquationLabelExtraction(unittest.TestCase):
    def test_extracts_qlearning_label(self):
        labels = _extract_equation_labels(QLEARNING_TEXT)
        self.assertIn("Q-learning", labels)

    def test_extracts_sarsa_label(self):
        labels = _extract_equation_labels(SARSA_TEXT)
        self.assertIn("Sarsa", labels)

    def test_extracts_both_labels_from_combined_text(self):
        combined = QLEARNING_TEXT + "\n\n" + SARSA_TEXT
        labels = _extract_equation_labels(combined)
        self.assertIn("Q-learning", labels)
        self.assertIn("Sarsa", labels)

    def test_no_label_invented_for_unlabeled_equation(self):
        labels = _extract_equation_labels("r + gamma * max_a' Q(s', a')")
        self.assertEqual(labels, [])

    def test_plain_prose_has_no_labels(self):
        labels = _extract_equation_labels("This method uses a replay buffer for training.")
        self.assertEqual(labels, [])


class TestQLearningSarsaExcerptSeparation(unittest.TestCase):
    """
    Adjacent chunks (same section, consecutive pages) both flagged
    contains_equation must NOT be merged into a single excerpt — each keeps
    its own excerpt boundary and its own equation label.
    """

    def setUp(self):
        chunks = [
            _chunk(
                "Asynchronous Methods for Deep Reinforcement Learning",
                QLEARNING_TEXT, section="Algorithms", page=4, contains_equation=True,
            ),
            _chunk(
                "Asynchronous Methods for Deep Reinforcement Learning",
                SARSA_TEXT, section="Algorithms", page=5, contains_equation=True,
            ),
        ]
        trace = []
        self.ctx = _build_context_block(chunks, trace)

    def test_two_separate_excerpts_emitted(self):
        self.assertEqual(self.ctx.count("[EXCERPT "), 2)

    def test_qlearning_target_not_blended_with_sarsa_target_in_one_block(self):
        # Split into excerpt blocks (drop the paper-header preamble before
        # the first "[EXCERPT ") and verify no single block contains both
        # equations' distinguishing terms (max_a' belongs only to Q-learning).
        blocks = self.ctx.split("[EXCERPT ")[1:]
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            # Each block should contain exactly one of the two equations, not both.
            self.assertFalse(QLEARNING_TEXT in block and SARSA_TEXT in block)

    def test_each_excerpt_carries_its_own_equation_label(self):
        self.assertIn("Equation labels: Q-learning", self.ctx)
        self.assertIn("Equation labels: Sarsa", self.ctx)

    def test_qlearning_and_sarsa_targets_are_textually_distinct_in_context(self):
        # Sanity: the two targets differ (max_a' vs no max) so a faithful
        # model has the information needed to distinguish them.
        self.assertIn("max_a'", self.ctx)
        self.assertIn(QLEARNING_TEXT, self.ctx)
        self.assertIn(SARSA_TEXT, self.ctx)


class TestPromptEnforcesPerEquationAttribution(unittest.TestCase):
    def setUp(self):
        chunks = [
            _chunk(
                "Asynchronous Methods for Deep Reinforcement Learning",
                QLEARNING_TEXT, section="Algorithms", page=4, contains_equation=True,
            ),
            _chunk(
                "Asynchronous Methods for Deep Reinforcement Learning",
                SARSA_TEXT, section="Algorithms", page=5, contains_equation=True,
            ),
        ]
        trace = []
        ctx = _build_context_block(chunks, trace)
        self.prompt = _build_adaptive_prompt(
            "Distinguish the Q-learning target from the Sarsa target.", ctx, "COMPARATIVE", trace
        )

    def test_prompt_instructs_not_to_share_equations_across_methods(self):
        p = self.prompt.lower()
        self.assertIn("equation labels", p)
        self.assertIn("do not attach it to, or reuse it for, any other method", p)

    def test_prompt_warns_against_assuming_shared_equations_for_similar_methods(self):
        self.assertIn(
            "never assume two methods share the same equation just because they are structurally similar",
            self.prompt.lower(),
        )

    def test_context_block_still_present_in_prompt(self):
        self.assertIn("Q-learning", self.prompt)
        self.assertIn("Sarsa", self.prompt)


if __name__ == "__main__":
    unittest.main()
