"""
Regression test -- ENUM_LIST prompt depth (algorithm/method list questions).

Failure mode captured in forensic investigation:
  Question: "What algorithms are proposed for AI-based power grid voltage control?"
  The pipeline retrieved DQN, DDPG, SAC, and imitation learning from the correct paper,
  but the answer (depth=CONCISE) omitted several algorithms.

Fix: _detect_answer_depth() now returns ENUM_LIST for "what algorithms / what methods /
     what approaches / what techniques / what models" questions.
     _build_adaptive_prompt() renders step-by-step enumeration instructions for ENUM_LIST.

These tests verify:
  1. The failing question and similar phrasing yields answer_depth == ENUM_LIST.
  2. ENUM_LIST does NOT fire for unrelated question forms.
  3. The generated prompt for an ENUM_LIST question contains the enumeration directives
     (scan, enumerate, explain, synthesis) ensuring the LLM is explicitly instructed
     to collect ALL named entities.
  4. CONCISE is NOT assigned to algorithm/method list questions.
"""

import unittest
from unittest.mock import patch

from retrieval.query_analyzer import detect_question_type, _detect_answer_depth
import agents.doc_agent as doc_agent


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_chunk(i, title, content):
    return {
        "id": f"chunk_{i}",
        "content": content,
        "metadata": {
            "hash": f"hash_{i}",
            "paper_title": title,
            "section": "3. Methods",
            "page_start": i,
            "page_end": i,
        },
        "score": 4.0 - i * 0.1,
    }


# ---------------------------------------------------------------------------
# 1. Depth detection -- positive cases
# ---------------------------------------------------------------------------

class TestEnumListDepthDetection(unittest.TestCase):
    """ENUM_LIST fires for questions that ask for a list of named methods/algorithms."""

    _ENUM_QUESTIONS = [
        "What algorithms are proposed for AI-based power grid voltage control?",
        "What methods are used in this system?",
        "What approaches does the paper present?",
        "Which techniques are applied in the experiments?",
        "What models are evaluated for text classification?",
        "What frameworks are compared in the study?",
        "What strategies are proposed to reduce energy consumption?",
        "Which algorithms were tested on the benchmark?",
        "What scheme is used for the scheduling problem?",
    ]

    def test_algorithm_list_question_yields_enum_list(self):
        """The exact failing question must yield ENUM_LIST, not CONCISE."""
        q = "What algorithms are proposed for AI-based power grid voltage control?"
        detect_question_type.cache_clear()
        result = detect_question_type(q)
        self.assertEqual(
            result["answer_depth"],
            "ENUM_LIST",
            f"Expected ENUM_LIST for '{q}', got '{result['answer_depth']}'"
        )

    def test_all_enum_list_questions_yield_enum_list(self):
        for q in self._ENUM_QUESTIONS:
            with self.subTest(q=q):
                depth = _detect_answer_depth(q.lower())
                self.assertEqual(
                    depth,
                    "ENUM_LIST",
                    f"Expected ENUM_LIST for '{q}', got '{depth}'"
                )

    def test_enum_list_not_assigned_concise(self):
        """No algorithm/method list question should receive CONCISE depth."""
        for q in self._ENUM_QUESTIONS:
            with self.subTest(q=q):
                depth = _detect_answer_depth(q.lower())
                self.assertNotEqual(
                    depth,
                    "CONCISE",
                    f"CONCISE incorrectly assigned to list question: '{q}'"
                )


# ---------------------------------------------------------------------------
# 2. Depth detection -- negative cases (should NOT yield ENUM_LIST)
# ---------------------------------------------------------------------------

class TestEnumListDoesNotFire(unittest.TestCase):
    """ENUM_LIST must not bleed into non-list questions."""

    _NON_ENUM_QUESTIONS = [
        "How does the reward function work?",
        "Why does the agent fail in sparse-reward settings?",
        "What is the learning rate used in training?",
        "Compare DQN and DDPG performance.",
        "Give an overview of reinforcement learning.",
        "What is the main contribution of this paper?",
    ]

    def test_non_list_questions_do_not_yield_enum_list(self):
        for q in self._NON_ENUM_QUESTIONS:
            with self.subTest(q=q):
                depth = _detect_answer_depth(q.lower())
                self.assertNotEqual(
                    depth,
                    "ENUM_LIST",
                    f"ENUM_LIST incorrectly assigned to non-list question: '{q}'"
                )


# ---------------------------------------------------------------------------
# 3. Prompt content -- ENUM_LIST instructions must appear in the built prompt
# ---------------------------------------------------------------------------

class TestEnumListPromptContent(unittest.TestCase):
    """
    Verify that when answer_depth == ENUM_LIST, the assembled prompt contains
    the four-step enumeration directives that force complete entity extraction.
    """

    def _make_chunks(self):
        return [
            _make_chunk(i, "Power Grid RL Paper", f"Content about algorithm {i}")
            for i in range(1, 5)
        ]

    @patch("agents.doc_agent.generate")
    def test_enum_list_prompt_contains_enumeration_directives(self, mock_generate):
        mock_generate.return_value = "DQN and DDPG are proposed [Paper: X, Section: 3, Page 1]."
    
        q = "What algorithms are proposed for AI-based power grid voltage control?"
        chunks = self._make_chunks()
    
        detect_question_type.cache_clear()
        doc_agent.run(q, chunks, request_id="test_enum_list_prompt")
    
        self.assertTrue(mock_generate.called, "generate() must be called")
        prompt_arg = mock_generate.call_args[0][0]
    
        self.assertIn("For ENUM_LIST questions", prompt_arg,
                      "ENUM_LIST prompt must contain the enumeration directives")
        # These strings are taken verbatim from the ENUM_LIST branch in
        # agents/doc_agent._build_adaptive_prompt() (lowercase 'd', "prohibit" phrasing).
        self.assertIn("directly enumerate the requested entities", prompt_arg,
                      "ENUM_LIST prompt must instruct the model to enumerate entities")
        self.assertIn("prohibit separate explanations for every entity", prompt_arg,
                      "ENUM_LIST prompt must prohibit per-entity explanations")

    @patch("agents.doc_agent.generate")
    def test_enum_list_not_assigned_concise(self, mock_generate):
        """'What is' should not trigger ENUM_LIST."""
        mock_generate.return_value = "It is an algorithm."
        q = "What is DQN?"
        chunks = self._make_chunks()
        detect_question_type.cache_clear()
        doc_agent.run(q, chunks, request_id="test_concise_no_enum")
        
        prompt_arg = mock_generate.call_args[0][0]
        self.assertNotIn("For ENUM_LIST questions", prompt_arg)

    @patch("agents.doc_agent.generate")
    def test_method_question_also_gets_enum_list_prompt(self, mock_generate):
        """'What methods are used' must also trigger ENUM_LIST instructions."""
        mock_generate.return_value = "Methods A and B are used."
        q = "What methods are used in this framework?"
        chunks = self._make_chunks()
        detect_question_type.cache_clear()
        doc_agent.run(q, chunks, request_id="test_methods_enum_list")
    
        prompt_arg = mock_generate.call_args[0][0]
        self.assertIn("For ENUM_LIST questions", prompt_arg)


if __name__ == "__main__":
    unittest.main()