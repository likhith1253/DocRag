import numpy as np
from unittest.mock import patch

from agents.orchestrator import Orchestrator, answer, CANNOT_FIND_RESPONSE


class _FakeVectorManager:
    def search(self, query, top_k=30, metadata_filters=None, request_id="default"):
        chunks = [
            {
                "content": "The paper states the answer explicitly in this excerpt.",
                "metadata": {
                    "hash": "low-score-hash",
                    "file": "paper_a.pdf",
                    "paper_title": "Paper A",
                    "section": "Results",
                    "page_start": 7,
                    "page_end": 7,
                },
                "score": 0.12,
                "id": "chunk-low-score",
                "vector": [0.0, 1.0, 0.0],
            }
        ]
        timing = {
            "embedding_ms": 0.0,
            "qdrant_ms": 0.0,
            "query_vector": np.zeros(3, dtype=np.float32),
        }
        return chunks, timing


def test_low_score_chunks_still_reach_llm():
    orch = Orchestrator()
    orch.v_manager = _FakeVectorManager()

    try:
        with patch("agents.orchestrator.mmr_rerank", side_effect=lambda *args, **kwargs: args[1]), \
             patch("agents.orchestrator.rerank_cross_encoder", side_effect=lambda *args, **kwargs: args[1]), \
             patch("agents.orchestrator.doc_agent.run", return_value="Grounded answer") as mock_run:
            ans, latency_breakdown, chunks, citations = answer(
                "What does the paper explicitly state?",
                repo_id="repo-low-score",
                request_id="test-low-score-regression",
            )

        assert ans == "Grounded answer"
        assert ans != CANNOT_FIND_RESPONSE
        assert mock_run.called
        assert len(chunks) == 1
        assert len(citations) == 1
        assert latency_breakdown["llm_ms"] >= 0
    finally:
        orch.v_manager = None
