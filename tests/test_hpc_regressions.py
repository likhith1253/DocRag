import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from storage.vector_store import VectorStoreManager
from retrieval.paper_matcher import match_papers_in_query, classify_paper_scope, get_collection_papers
import agents.orchestrator as orchestrator
from agents.doc_agent import _extract_equation_labels, _build_adaptive_prompt


class TestHPCRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection = "collection_71e2cffe-8756-4ff3-b35c-52fc94babdd4"
        cls.vman = VectorStoreManager(collection_name=cls.collection)
        cls.titles = get_collection_papers(cls.vman)

    def test_01_dqn_paper_matcher_and_isolation(self):
        """DQN query matches Playing Atari and enforces single paper isolation."""
        query = "What preprocessing is used in DQN to represent game screens?"
        matches = match_papers_in_query(query, self.titles)
        self.assertTrue(len(matches) >= 1)
        matched_title = matches[0][0]
        self.assertIn("Playing Atari", matched_title)
        self.assertEqual(classify_paper_scope(matches), "single")

        state = {
            "question": query,
            "repo_id": self.collection,
            "filters": {},
            "retrieval_mode": "single",
            "request_id": "test_dqn_01",
        }
        res = orchestrator.retrieve_node(state)
        chunks = res.get("retrieved_chunks", [])
        self.assertTrue(len(chunks) > 0, "DQN query must retrieve nonzero chunks")

        # Strict single-paper isolation: every chunk must be from Playing Atari
        for c in chunks:
            paper = c.get("metadata", {}).get("paper_title") or c.get("metadata", {}).get("file") or ""
            self.assertIn("Playing Atari", paper, f"Contaminating chunk found: {paper}")

        # Verify preprocessing evidence is retained (210x160 or grayscale or 84x84 or frames)
        combined_text = " ".join(c.get("content", "") for c in chunks)
        has_preprocessing_details = any(term in combined_text for term in ["210", "160", "84", "grayscale", "gray-scale"])
        self.assertTrue(has_preprocessing_details, "Preprocessing evidence must be retained in top chunks")

    def test_02_multi_paper_isolation_dqn_a3c_sac(self):
        """Multi-paper comparison query naming DQN, A3C, SAC matches exactly 3 papers and excludes all others."""
        query = "Compare DQN, A3C and SAC in terms of stability and sample efficiency."
        matches = match_papers_in_query(query, self.titles)
        self.assertEqual(len(matches), 3, f"Expected exactly 3 matches, got: {matches}")
        matched_titles = [m[0] for m in matches]
        self.assertTrue(any("Playing Atari" in t for t in matched_titles))
        self.assertTrue(any("Asynchronous" in t for t in matched_titles))
        self.assertTrue(any("Soft Actor-Critic" in t for t in matched_titles))
        self.assertEqual(classify_paper_scope(matches), "multi")

        state = {
            "question": query,
            "repo_id": self.collection,
            "filters": {},
            "retrieval_mode": "single",
            "request_id": "test_multi_02",
        }
        res = orchestrator.retrieve_node(state)
        chunks = res.get("retrieved_chunks", [])
        self.assertTrue(len(chunks) > 0, "Multi-paper query must retrieve chunks")

        # Defense-in-depth: every single chunk must be from one of the 3 requested papers
        for c in chunks:
            paper = c.get("metadata", {}).get("paper_title") or c.get("metadata", {}).get("file") or ""
            is_valid = any(req in paper for req in ["Playing Atari", "Asynchronous", "Soft Actor-Critic"])
            self.assertTrue(is_valid, f"Unexpected paper in multi-paper query: {paper}")

    def test_03_world_models_vector_search(self):
        """World Models query finds chunks even when default or collection ID is used."""
        query = "What is the architecture of World Models and its Controller component?"
        matches = match_papers_in_query(query, self.titles)
        self.assertTrue(len(matches) >= 1)
        self.assertEqual(matches[0][0], "World Models")

        state = {
            "question": query,
            "repo_id": self.collection,
            "filters": {},
            "retrieval_mode": "single",
            "request_id": "test_wm_03",
        }
        res = orchestrator.retrieve_node(state)
        chunks = res.get("retrieved_chunks", [])
        self.assertTrue(len(chunks) > 0, "World Models must retrieve nonzero chunks")
        for c in chunks:
            paper = c.get("metadata", {}).get("paper_title") or c.get("metadata", {}).get("file") or ""
            self.assertEqual(paper, "World Models")

    def test_04_a3c_target_distinction_and_labeling(self):
        """Verify equation labeling distinguishes Q-learning vs Sarsa targets in A3C."""
        sarsa_text = (
            "Asynchronous one-step Sarsa: The asynchronous one-step Sarsa algorithm is the same as "
            "asynchronous one-step Q-learning as given in Algorithm 1 except that it uses a different "
            "target value for Q(s, a). The target value used by one-step Sarsa is r + \\gamma Q(s', a'; \\theta^-) "
            "where a' is the action taken in state s'. We again use a target network."
        )
        labels = _extract_equation_labels(sarsa_text)
        self.assertTrue(any("Sarsa" in l for l in labels), "Sarsa target must be extracted as an equation label")

        prompt = _build_adaptive_prompt("What is the difference between Q-learning and Sarsa targets in A3C?", "", "DETAILED", [])
        self.assertIn("Q-learning target", prompt)
        self.assertIn("Sarsa target", prompt)
        self.assertIn("max", prompt)

    def test_05_sac_objective_verbatim_grounding(self):
        """Verify SAC maximum entropy objective prompt rule mandates verbatim Equation 1."""
        sac_text = (
            "3.2. Maximum Entropy Reinforcement Learning\n"
            "Standard RL maximizes expected sum of rewards. We consider a more general maximum entropy objective:\n"
            "J(\\pi) = \\sum_{t=0}^T E_{(s_t, a_t)~\\rho_\\pi} [r(s_t, a_t) + \\alpha H(\\pi(\\cdot|s_t))]\n"
            "The temperature parameter \\alpha determines relative importance of the entropy term."
        )
        labels = _extract_equation_labels(sac_text)
        self.assertTrue(any("Maximum Entropy" in l for l in labels))

        prompt = _build_adaptive_prompt("What is the objective function of Soft Actor-Critic?", "", "DETAILED", [])
        self.assertIn("Soft Actor-Critic (SAC) Maximum Entropy Objective", prompt)
        self.assertIn("alpha", prompt)


if __name__ == "__main__":
    unittest.main()
