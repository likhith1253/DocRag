"""
Lightweight retrieval-isolation tests for agents.orchestrator.retrieve_node.

Uses the existing agents.orchestrator._v_manager_override test seam (already
used by the class-based Orchestrator API) to inject a fake, in-memory vector
store instead of hitting real Qdrant/embedding models, and patches
mmr_rerank/rerank_cross_encoder to simple pass-throughs so no ML model is
loaded. This tests the actual retrieval routing/isolation logic in
retrieve_node, not just the paper_matcher helper functions in isolation.
"""

import unittest
from unittest.mock import patch
import numpy as np

import agents.orchestrator as orchestrator
from retrieval.paper_matcher import invalidate_paper_cache


def _chunk(paper_title, text, page=1, section="Body"):
    return {
        "content": text,
        "metadata": {
            "collection_id": "test_col",
            "paper_title": paper_title,
            "file": paper_title.replace(" ", "_") + ".pdf",
            "section": section,
            "page_start": page,
            "page_end": page,
            "hash": f"{paper_title}::{text}::{page}",
            "chunk_type": "TEXT",
        },
    }


class FakeVManager:
    """In-memory stand-in for storage.vector_store.VectorStoreManager."""

    def __init__(self, chunks, collection_name="fake_collection", starved_papers=None):
        self._chunks = chunks
        self.collection_name = collection_name
        self.search_calls = []  # records (query, metadata_filters) for assertions
        # Papers that are known (appear in get_all_chunks(), so they're a
        # valid candidate for paper_matcher) but whose filtered search
        # always returns zero results — simulates a real paper that's
        # indexed but has no chunk matching this particular query.
        self._starved_papers = starved_papers or set()

    def count(self):
        return len(self._chunks)

    def get_all_chunks(self):
        return self._chunks

    def search(self, query, top_k=30, metadata_filters=None, request_id="default"):
        self.search_calls.append((query, dict(metadata_filters) if metadata_filters else None))
        if metadata_filters and metadata_filters.get("paper_title") in self._starved_papers:
            timing = {"embedding_ms": 0.1, "qdrant_ms": 0.1, "query_vector": np.zeros(8, dtype=np.float32)}
            return [], timing
        results = []
        for c in self._chunks:
            if metadata_filters:
                meta = c.get("metadata", {})
                if not all(meta.get(k) == v for k, v in metadata_filters.items()):
                    continue
            results.append({**c, "score": 1.0, "id": c["metadata"]["hash"]})
        timing = {
            "embedding_ms": 0.1,
            "qdrant_ms": 0.1,
            "query_vector": np.zeros(8, dtype=np.float32),
        }
        return results[:top_k], timing


def _passthrough_mmr(query, chunks, top_k=40, query_vector=None, request_id="default"):
    return chunks[:top_k]


def _passthrough_ce(query, chunks, top_k=5, request_id="default"):
    return chunks[:top_k]


CORPUS = [
    _chunk("Playing Atari with Deep Reinforcement Learning", "DQN uses experience replay.", page=2),
    _chunk("Playing Atari with Deep Reinforcement Learning", "Training on Atari 2600 games.", page=3),
    _chunk("Asynchronous Methods for Deep Reinforcement Learning", "A3C uses parallel actor-learners.", page=2),
    _chunk("Asynchronous Methods for Deep Reinforcement Learning", "Asynchronous gradient updates.", page=4),
    _chunk("Soft Actor-Critic", "SAC maximizes entropy-regularized reward.", page=3),
    _chunk("Soft Actor-Critic", "Off-policy training with a replay buffer.", page=5),
    _chunk("A Deep Reinforcement Learning Approach for Ramp Metering", "Ramp metering reduces congestion.", page=1),
]


@patch("agents.orchestrator.rerank_cross_encoder", side_effect=_passthrough_ce)
@patch("agents.orchestrator.mmr_rerank", side_effect=_passthrough_mmr)
class TestRetrievalPaperIsolation(unittest.TestCase):
    def setUp(self):
        invalidate_paper_cache()
        orchestrator._v_manager_override = FakeVManager(CORPUS)

    def tearDown(self):
        orchestrator._v_manager_override = None
        invalidate_paper_cache()

    def _base_state(self, question):
        return {
            "request_id": "test-req",
            "question": question,
            "repo_id": "",
            "filters": {},
            "retrieval_mode": "single",
        }

    def test_single_paper_query_isolates_to_one_paper(self, mock_ce, mock_mmr):
        state = self._base_state("Explain the training procedure used in Soft Actor-Critic.")
        result = orchestrator.retrieve_node(state)
        chunks = result["retrieved_chunks"]
        self.assertTrue(chunks)
        papers = {c["metadata"]["paper_title"] for c in chunks}
        self.assertEqual(papers, {"Soft Actor-Critic"})

    def test_explicit_multi_paper_query_retrieves_all_requested(self, mock_ce, mock_mmr):
        query = (
            "Compare Playing Atari with Deep Reinforcement Learning, "
            "Asynchronous Methods for Deep Reinforcement Learning, and Soft Actor-Critic."
        )
        state = self._base_state(query)
        result = orchestrator.retrieve_node(state)
        chunks = result["retrieved_chunks"]
        papers = {c["metadata"]["paper_title"] for c in chunks}
        self.assertEqual(
            papers,
            {
                "Playing Atari with Deep Reinforcement Learning",
                "Asynchronous Methods for Deep Reinforcement Learning",
                "Soft Actor-Critic",
            },
        )

    def test_unrelated_paper_never_contaminates_explicit_multi_paper_result(self, mock_ce, mock_mmr):
        query = (
            "Compare Playing Atari with Deep Reinforcement Learning, "
            "Asynchronous Methods for Deep Reinforcement Learning, and Soft Actor-Critic."
        )
        state = self._base_state(query)
        result = orchestrator.retrieve_node(state)
        chunks = result["retrieved_chunks"]
        papers = {c["metadata"]["paper_title"] for c in chunks}
        self.assertNotIn("A Deep Reinforcement Learning Approach for Ramp Metering", papers)

    def test_general_collection_query_is_not_restricted_to_one_paper(self, mock_ce, mock_mmr):
        state = self._base_state("What papers discuss experience replay?")
        result = orchestrator.retrieve_node(state)
        chunks = result["retrieved_chunks"]
        papers = {c["metadata"]["paper_title"] for c in chunks}
        # Collection-wide query: evidence may legitimately span multiple
        # papers, and must NOT be silently pinned to a single paper_title.
        self.assertGreater(len(papers), 1)
        v_manager = orchestrator._v_manager_override
        self.assertIsNone(v_manager.search_calls[0][1], "Collection-wide query must not add a paper_title filter")

    def test_missing_requested_paper_is_reported_not_substituted(self, mock_ce, mock_mmr):
        # "Soft Actor-Critic" is a known, indexed paper (so it's still a
        # valid match candidate) but yields zero chunks for this specific
        # query — must be reported missing, never silently swapped for a
        # different paper's evidence.
        orchestrator._v_manager_override = FakeVManager(CORPUS, starved_papers={"Soft Actor-Critic"})
        query = "Compare Playing Atari with Deep Reinforcement Learning and Soft Actor-Critic."
        state = self._base_state(query)

        import io
        import contextlib
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            result = orchestrator.retrieve_node(state)
        self.assertIn("Insufficient/no evidence for requested paper(s): ['Soft Actor-Critic']", captured.getvalue())

        chunks = result["retrieved_chunks"]
        papers = {c["metadata"]["paper_title"] for c in chunks}
        self.assertIn("Playing Atari with Deep Reinforcement Learning", papers)
        self.assertNotIn("Soft Actor-Critic", papers)  # not substituted with something else
        # No other/unexpected paper silently filled the gap.
        self.assertEqual(papers, {"Playing Atari with Deep Reinforcement Learning"})

    def test_metadata_filter_used_for_each_paper_in_multi_query(self, mock_ce, mock_mmr):
        query = "Compare Playing Atari with Deep Reinforcement Learning and Soft Actor-Critic."
        state = self._base_state(query)
        orchestrator.retrieve_node(state)
        v_manager = orchestrator._v_manager_override
        filtered_titles = {
            filters["paper_title"]
            for _, filters in v_manager.search_calls
            if filters and "paper_title" in filters
        }
        self.assertEqual(
            filtered_titles,
            {"Playing Atari with Deep Reinforcement Learning", "Soft Actor-Critic"},
        )

    def test_explicit_filter_from_caller_bypasses_auto_detection(self, mock_ce, mock_mmr):
        # If the caller already pinned a paper_title filter, auto-detection
        # must not override it with a different (auto-matched) paper.
        state = self._base_state("Explain the training procedure used in Soft Actor-Critic.")
        state["filters"] = {"paper_title": "Playing Atari with Deep Reinforcement Learning"}
        result = orchestrator.retrieve_node(state)
        chunks = result["retrieved_chunks"]
        papers = {c["metadata"]["paper_title"] for c in chunks}
        self.assertEqual(papers, {"Playing Atari with Deep Reinforcement Learning"})


if __name__ == "__main__":
    unittest.main()
