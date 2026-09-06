import os
import sys
import unittest
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from storage.vector_store import VectorStoreManager
from retrieval.paper_matcher import match_papers_in_query, classify_paper_scope, get_collection_papers
import agents.orchestrator as orchestrator
import agents.doc_agent as doc_agent
from agents.doc_agent import (
    _extract_equation_labels,
    _build_adaptive_prompt,
    _build_context_block,
    _build_source_extracted_evidence,
    _validate_and_sanitize_claims,
    verify_high_risk_grounding,
)


class TestHPCRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from storage.vector_store import _get_config
        cfg = _get_config()
        cfg["qdrant_path"] = "./qdrant_storage"
        cls.collection = "collection_71e2cffe-8756-4ff3-b35c-52fc94babdd4"
        cls.vman = VectorStoreManager(collection_name=cls.collection)
        cls.titles = get_collection_papers(cls.vman)
        orchestrator._v_manager_override = cls.vman

    def setUp(self):
        from storage.vector_store import _get_config
        cfg = _get_config()
        cfg["qdrant_path"] = "./qdrant_storage"
        orchestrator._v_manager_override = self.vman

    @classmethod
    def tearDownClass(cls):
        orchestrator._v_manager_override = None

    # -----------------------------------------------------------------------
    # Test 1: A3C Q-learning max target vs Sarsa target distinction
    # -----------------------------------------------------------------------
    def test_01_a3c_qlearning_vs_sarsa_target_distinction(self):
        """A3C technical evidence keeps Q-learning max target distinct from Sarsa target."""
        raw_output = (
            "## Overview\n"
            "Asynchronous methods include one-step Q-learning and one-step Sarsa.\n"
            "## Detailed Explanation\n"
            "The Q-learning target is r + gamma Q(s', a'; theta-) where actions are chosen greedily, "
            "while the Sarsa target is r + gamma Q(s', a'; theta-) where a' is the action actually taken.\n"
        )
        # Pass through claim validator & sanitizer
        sanitized = _validate_and_sanitize_claims(raw_output, [], "What are the update targets for Q-learning and Sarsa in A3C?")
        
        self.assertIn("max", sanitized.lower(), "Q-learning target must contain max operator")
        self.assertIn("where a' is the action", sanitized, "Sarsa target must specify action a' taken")

        # Also verify the prompt contains the strict target distinction rule
        prompt = _build_adaptive_prompt("What are the update targets for Q-learning and Sarsa in A3C?", "", "DETAILED", [])
        self.assertIn("r + gamma * max_a' Q(s', a'; theta^-)", prompt)
        self.assertIn("r + gamma * Q(s', a'; theta^-)", prompt)

    # -----------------------------------------------------------------------
    # Test 2: DQN preprocessing frame count cannot be turned into 84 frames
    # -----------------------------------------------------------------------
    def test_02_dqn_preprocessing_frame_count_not_84(self):
        """DQN preprocessing answer cannot turn 84x84 into '84 frames'."""
        hallucinated_answer = (
            "## Overview\n"
            "The input preprocessing involves stacking 84 consecutive frames to capture movement."
        )
        sanitized = _validate_and_sanitize_claims(hallucinated_answer, [], "What preprocessing is used in DQN?")
        self.assertNotIn("84 consecutive frames", sanitized)
        self.assertIn("4 consecutive frames", sanitized)
        self.assertIn("84 × 84", sanitized)

    # -----------------------------------------------------------------------
    # Test 3: DQN preprocessing methodology chunk survives into final context
    # -----------------------------------------------------------------------
    def test_03_dqn_preprocessing_chunk_survives_to_final_context(self):
        """DQN preprocessing methodology chunk survives through FINAL prompt context."""
        query = "How are game screens preprocessed in Playing Atari with Deep Reinforcement Learning?"
        state = {
            "question": query,
            "repo_id": self.collection,
            "filters": {},
            "retrieval_mode": "single",
            "request_id": "test_dqn_preproc_survives",
        }
        res = orchestrator.retrieve_node(state)
        chunks = res.get("retrieved_chunks", [])
        self.assertTrue(len(chunks) > 0, "Must retrieve nonzero chunks for DQN query")

        # Find the specific methodology chunk on Page 5
        methodology_chunk = next(
            (c for c in chunks if "210 × 160" in c.get("content", "") and "84 × 84" in c.get("content", "")),
            None
        )
        self.assertIsNotNone(methodology_chunk, "Exact preprocessing chunk (210x160 -> 84x84) must survive into retrieved chunks")
        self.assertEqual(int(methodology_chunk.get("metadata", {}).get("page_start", 0)), 5)

        # Verify it enters context block
        context_block = _build_context_block(chunks, [])
        self.assertIn("210 × 160", context_block)
        self.assertIn("84 × 84", context_block)
        self.assertIn("last 4 frames", context_block)

    # -----------------------------------------------------------------------
    # Test 4: SAC Supporting Evidence cannot attribute equations to unrelated page
    # -----------------------------------------------------------------------
    def test_04_sac_supporting_evidence_no_fake_equation_attribution(self):
        """SAC Supporting Evidence cannot attribute generated equations to an unrelated page/figure."""
        # Simulated retrieved chunks for SAC: Page 7 is ablation study, Page 3 has objective
        sac_chunks = [
            {
                "content": (
                    "3.2. Maximum Entropy Reinforcement Learning\n"
                    "We consider a more general maximum entropy objective: "
                    "J(\\pi) = \\sum_{t=0}^T E_{(s_t, a_t)~\\rho_\\pi} [r(s_t, a_t) + \\alpha H(\\pi(\\cdot|s_t))]. "
                    "The temperature parameter \\alpha determines relative importance of entropy."
                ),
                "metadata": {
                    "paper_title": "Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor",
                    "section": "3.2. Maximum Entropy Reinforcement Learning",
                    "page_start": 3,
                    "page_end": 3,
                    "contains_equation": True,
                }
            },
            {
                "content": (
                    "5.2. Ablation Study\n"
                    "Figure 4 shows the ablation study over reward scaling and target smoothing parameter. "
                    "The results are averaged over 5 random seeds."
                ),
                "metadata": {
                    "paper_title": "Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor",
                    "section": "5.2 Ablation Study",
                    "page_start": 7,
                    "page_end": 7,
                    "contains_figure": True,
                }
            }
        ]

        # LLM generated output that hallucinated an invented Q-update on Page 7
        raw_llm_output = (
            "## Overview\nSAC maximizes entropy and reward.\n"
            "## Detailed Explanation\nIt optimizes expected return and entropy.\n"
            "## Supporting Evidence\n"
            "- [Paper: Soft Actor-Critic, Section: 5.2 Ablation Study, Page 7, Evidence: figure]:\n"
            "  Q(s, a) = r + gamma * (Q(s', a') - alpha * log pi(a'|s'))\n"
        )

        sanitized = _validate_and_sanitize_claims(raw_llm_output, sac_chunks, "What is the objective of SAC?")
        evidence_block = _build_source_extracted_evidence(sac_chunks, "What is the objective of SAC?")
        final_answer = sanitized + evidence_block

        # Ensure invented Q-update on Page 7 is NOT in the final answer
        self.assertNotIn("Q(s, a) = r + gamma * (Q(s', a') - alpha * log pi(a'|s'))", final_answer)
        # Ensure genuine objective equation from Page 3 IS in the Supporting Evidence
        self.assertIn("Page 3", evidence_block)
        self.assertIn("J(\\pi)", evidence_block)

    # -----------------------------------------------------------------------
    # Test 5: World Models keeps 867 CarRacing and 1088 VizDoom parameter counts tied to correct source chunks
    # -----------------------------------------------------------------------
    def test_05_world_models_parameter_counts_attribution(self):
        """World Models keeps 867 CarRacing and 1088 VizDoom parameter counts tied to their correct source chunks."""
        raw_output = (
            "## Overview\n"
            "In World Models, the linear controller has 1,088 controller parameters as described in Section 3.3 on Page 5 for CarRacing."
        )
        sanitized = _validate_and_sanitize_claims(raw_output, [], "What are the controller parameters in World Models?")
        self.assertIn("867 controller parameters", sanitized)
        self.assertIn("Section 3.3, Page 5", sanitized)
        self.assertIn("1,088 parameters belongs to VizDoom", sanitized)

    # -----------------------------------------------------------------------
    # Test 6: Figure-only textual evidence produces an explicit visual-unavailable caveat
    # -----------------------------------------------------------------------
    def test_06_figure_only_textual_evidence_caveat(self):
        """Figure-only textual evidence produces an explicit visual-unavailable caveat."""
        raw_output = (
            "## Overview\n"
            "Figure 2 illustrates the interaction between V, M, and C components."
        )
        sanitized = _validate_and_sanitize_claims(raw_output, [], "Explain the architecture workflow in Figure 2 of World Models.")
        self.assertIn("visual figure itself was not inspected", sanitized)

    # -----------------------------------------------------------------------
    # Test 7: Multi-paper answer cannot assign A3C's softmax-policy/value architecture to DQN
    # -----------------------------------------------------------------------
    def test_07_multi_paper_no_dqn_softmax_linear_policy(self):
        """Multi-paper answer cannot assign A3C's softmax-policy/value architecture to DQN."""
        raw_output = (
            "## Differences\n"
            "DQN uses a softmax-policy + linear-value output, whereas other algorithms differ."
        )
        sanitized = _validate_and_sanitize_claims(raw_output, [], "Compare DQN and A3C architectures.")
        self.assertNotIn("DQN uses a softmax-policy + linear-value output", sanitized)
        self.assertIn("action-values", sanitized)
        self.assertIn("epsilon-greedy", sanitized)

    # -----------------------------------------------------------------------
    # Test 8: A3C correctly states asynchronous actors replace reliance on experience replay
    # -----------------------------------------------------------------------
    def test_08_a3c_experience_replay_replacement(self):
        """A3C correctly states that asynchronous actors replace reliance on experience replay when that evidence is retrieved."""
        raw_output = (
            "## Overview\n"
            "For A3C, experience replay is not explicitly mentioned in the text."
        )
        sanitized = _validate_and_sanitize_claims(raw_output, [], "Does A3C use experience replay?")
        self.assertNotIn("replay is not explicitly mentioned", sanitized)
        self.assertIn("replace reliance on experience replay", sanitized)

    # -----------------------------------------------------------------------
    # Test 9: DQN evaluation preserves seven games vs state-of-the-art on six
    # -----------------------------------------------------------------------
    def test_09_dqn_evaluation_seven_games_sota_six(self):
        """DQN evaluation preserves seven games vs state-of-the-art on six."""
        raw_output = (
            "## Experiments\n"
            "The authors evaluated on six games with deep reinforcement learning."
        )
        sanitized = _validate_and_sanitize_claims(raw_output, [], "How many games was DQN evaluated on?")
        self.assertIn("seven Atari games", sanitized)
        self.assertIn("state-of-the-art results on six", sanitized)

    # -----------------------------------------------------------------------
    # Test 10: Every generated high-risk numeric/equation claim must have matching retrieved source chunk
    # -----------------------------------------------------------------------
    def test_10_high_risk_claims_grounded_to_source_chunks(self):
        """Every generated high-risk numeric/equation claim must have a matching retrieved source chunk."""
        retrieved_chunks = [
            {
                "content": "The linear controller model has 867 parameters. We crop to an 84 × 84 region and stack 4 frames.",
                "metadata": {"page_start": 5, "page_end": 5}
            }
        ]
        
        # Answer with numbers supported by chunk: 867, 84, 4
        supported_answer = "The model uses 867 parameters and an 84 × 84 spatial size with 4 frames on Page 5."
        grounding_result = verify_high_risk_grounding(supported_answer, retrieved_chunks)
        self.assertTrue(grounding_result["is_grounded"], f"Expected supported answer to be grounded, got: {grounding_result}")

        # Answer with hallucinated numbers NOT in chunk: 99999 parameters
        unsupported_answer = "The model uses 99999 parameters on Page 5."
        ungrounded_result = verify_high_risk_grounding(unsupported_answer, retrieved_chunks)
        self.assertFalse(ungrounded_result["is_grounded"])
        self.assertIn("99999", ungrounded_result["ungrounded_numbers"])


if __name__ == "__main__":
    unittest.main()
