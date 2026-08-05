"""
Unit tests for DocAgent Prompt Builder Contract and Retrieval Topic Concentration Filtering.
Verifies assertions for chunk count, deduplication, excerpt count, prompt size, and topic concentration.
"""

import unittest
from unittest.mock import patch, MagicMock
import agents.doc_agent as doc_agent
from retrieval.cross_encoder_rerank import rerank_cross_encoder


class TestDocAgentContract(unittest.TestCase):

    def setUp(self):
        self.sample_chunks = [
            {
                "id": f"chunk_{i}",
                "content": f"This is valid content for chunk {i} describing FPGA acceleration.",
                "metadata": {
                    "hash": f"hash_{i}",
                    "paper_title": "FPGA Deep Learning Systems",
                    "section": "3. Hardware Design",
                    "page_start": i,
                    "page_end": i,
                },
                "score": 4.5 - (i * 0.1),
            }
            for i in range(1, 9)
        ]

    @patch("agents.doc_agent.generate")
    def test_valid_prompt_assembly_and_assertions(self, mock_generate):
        mock_generate.return_value = "FPGA acceleration increases efficiency [Excerpt 1]."
        
        result = doc_agent.run("What is FPGA performance?", self.sample_chunks, request_id="test_contract_valid")
        
        # Phase 6: answer now includes appended confidence block — check prefix
        self.assertTrue(result.startswith("FPGA acceleration increases efficiency [Excerpt 1]."))
        self.assertTrue(mock_generate.called)

    def test_chunk_cap_assertion_failure(self):
        # 9 chunks exceeds default cap of 8
        over_cap_chunks = self.sample_chunks + [
            {
                "id": "chunk_9",
                "content": "Extra chunk 9",
                "metadata": {"hash": "hash_9", "paper_title": "Extra Paper"},
                "score": 1.0,
            }
        ]
        with self.assertRaises(AssertionError) as ctx:
            doc_agent.run("Question?", over_cap_chunks, request_id="test_cap_fail")
        self.assertIn("PIPELINE CONTRACT VIOLATION", str(ctx.exception))
        self.assertIn("agent_chunk_cap", str(ctx.exception))

    def test_duplicate_chunk_assertion_failure(self):
        # Duplicate chunk IDs
        duplicate_chunks = self.sample_chunks[:7] + [self.sample_chunks[0]]
        with self.assertRaises(AssertionError) as ctx:
            doc_agent.run("Question?", duplicate_chunks, request_id="test_dup_fail")
        self.assertIn("Input valid_chunks contains duplicates", str(ctx.exception))

    def test_prompt_explosion_assertion_failure(self):
        # Massive chunk content exceeding 100k chars total across prompt
        huge_chunks = [
            {
                "id": f"chunk_{i}",
                "content": "A" * 15000,  # 15,000 chars each
                "metadata": {"hash": f"hash_{i}", "paper_title": "Huge Paper"},
                "score": 4.0,
            }
            for i in range(1, 8)
        ]
        # Bypass per-excerpt cap and explosion guard to test prompt explosion assertion directly
        with patch("agents.doc_agent._MAX_EXCERPT_CHARS", 20000), patch("agents.doc_agent._PROMPT_EXPLOSION_THRESHOLD", 200000):
            with self.assertRaises(AssertionError) as ctx:
                doc_agent.run("Question?", huge_chunks, request_id="test_explosion_fail")
            self.assertIn("PROMPT EXPLOSION FATAL ERROR", str(ctx.exception))

    @patch("retrieval.cross_encoder_rerank._cross_encoder_cache")
    def test_topic_concentration_filter(self, mock_cache_dict):
        # Mock CrossEncoder predict method
        mock_model = MagicMock()
        # Chunks 1-3 (FPGA paper) get high scores (4.5, 4.2, 4.0)
        # Chunks 4-6 (SAC / Atari / Power Grid off-topic papers) get low scores (1.0, 0.5, -3.0)
        mock_model.predict.return_value = [4.5, 4.2, 4.0, 1.0, 0.5, -3.0]
        mock_cache_dict.__contains__.return_value = True
        mock_cache_dict.__getitem__.return_value = mock_model

        input_chunks = [
            {
                "id": "c1",
                "content": "FPGA logic blocks",
                "metadata": {"paper_title": "FPGA Paper", "section": "1. Intro"},
                "score": 0.9,
            },
            {
                "id": "c2",
                "content": "FPGA memory bandwidth",
                "metadata": {"paper_title": "FPGA Paper", "section": "2. Design"},
                "score": 0.85,
            },
            {
                "id": "c3",
                "content": "FPGA DSP slices",
                "metadata": {"paper_title": "FPGA Paper", "section": "3. Logic"},
                "score": 0.8,
            },
            {
                "id": "c4",
                "content": "Soft Actor Critic entropy",
                "metadata": {"paper_title": "SAC Paper", "section": "4. RL"},
                "score": 0.4,
            },
            {
                "id": "c5",
                "content": "Atari Breakout score",
                "metadata": {"paper_title": "Atari Paper", "section": "5. Games"},
                "score": 0.3,
            },
            {
                "id": "c6",
                "content": "Power Grid load balancing",
                "metadata": {"paper_title": "Power Grid Paper", "section": "6. Grid"},
                "score": 0.1,
            },
        ]

        reranked = rerank_cross_encoder("FPGA hardware architecture", input_chunks, top_k=5, request_id="test_filter")
        
        # Verify that off-topic isolated outlier chunks were pruned
        paper_titles = [c.get("metadata", {}).get("paper_title") for c in reranked]
        self.assertIn("FPGA Paper", paper_titles)
        self.assertNotIn("Power Grid Paper", paper_titles)


if __name__ == "__main__":
    unittest.main()
