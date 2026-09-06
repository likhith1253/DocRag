"""
Regression tests for Phase 3 Test 5 (multi-paper comparison contamination)
and the related single-paper isolation failure in Test 2 (DQN).

Root cause: when retrieval for an explicit single/multi-paper query produced
zero chunks (e.g. every per-paper filtered search came back starved), the old
retrieve_node fell through to an UNRESTRICTED collection-wide search with no
paper filter at all — silently substituting whatever was globally closest,
including a totally unrelated paper. That is exactly how
"A Deep Reinforcement Learning Approach for Ramp Metering" could appear in
the result set for a query that only asked about three specific RL papers.

Fixes verified here (agents/orchestrator.py):
  - The unrestricted collection-wide fallback is now skipped entirely for
    paper_scope in ("single", "multi") — an explicit paper request must
    report missing evidence, never backfill from an unrelated paper.
  - _enforce_paper_isolation is a defense-in-depth hard filter that drops any
    chunk not from a requested paper, regardless of how it got there.
"""

import unittest
from unittest.mock import patch
import numpy as np

import agents.orchestrator as orchestrator
from agents.orchestrator import _enforce_paper_isolation
from retrieval.paper_matcher import invalidate_paper_cache


def _chunk(paper_title, text, page=1, section="Body", **evidence_flags):
    meta = {
        "collection_id": "test_col",
        "paper_title": paper_title,
        "file": paper_title.replace(" ", "_") + ".pdf",
        "section": section,
        "page_start": page,
        "page_end": page,
        "hash": f"{paper_title}::{text}::{page}",
        "chunk_type": "TEXT",
    }
    meta.update(evidence_flags)
    return {"content": text, "metadata": meta}


class FakeVManager:
    """
    Same in-memory stand-in as test_retrieval_paper_isolation.py, with an
    added `starve_all` mode simulating every requested paper's filtered
    search returning zero results (the exact scenario that used to trigger
    the unrestricted fallback).
    """

    def __init__(self, chunks, collection_name="fake_collection", starve_all=False):
        self._chunks = chunks
        self.collection_name = collection_name
        self.search_calls = []
        self.starve_all = starve_all

    def count(self):
        return len(self._chunks)

    def get_all_chunks(self):
        return self._chunks

    def search(self, query, top_k=30, metadata_filters=None, request_id="default"):
        self.search_calls.append((query, dict(metadata_filters) if metadata_filters else None))
        timing = {"embedding_ms": 0.1, "qdrant_ms": 0.1, "query_vector": np.zeros(8, dtype=np.float32)}
        if self.starve_all and metadata_filters and "paper_title" in metadata_filters:
            return [], timing
        results = []
        for c in self._chunks:
            if metadata_filters:
                meta = c.get("metadata", {})
                if not all(meta.get(k) == v for k, v in metadata_filters.items()):
                    continue
            results.append({**c, "score": 1.0, "id": c["metadata"]["hash"]})
        return results[:top_k], timing


def _passthrough_mmr(query, chunks, top_k=40, query_vector=None, request_id="default"):
    return chunks[:top_k]


def _passthrough_ce(query, chunks, top_k=5, request_id="default"):
    return chunks[:top_k]


DQN_TITLE = "Playing Atari with Deep Reinforcement Learning"
A3C_TITLE = "Asynchronous Methods for Deep Reinforcement Learning"
SAC_TITLE = "Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor"
RAMP_TITLE = "A Deep Reinforcement Learning Approach for Ramp Metering"

THREE_PAPER_CORPUS = [
    _chunk(DQN_TITLE, "Raw frames are preprocessed and stacked as input to the CNN.", page=3),
    _chunk(DQN_TITLE, "Experience replay stores transitions for later reuse.", page=4),
    _chunk(A3C_TITLE, "Q-learning: r + gamma * max_a' Q(s', a')", page=4, contains_equation=True),
    _chunk(A3C_TITLE, "Sarsa: r + gamma * Q(s', a')", page=5, contains_equation=True),
    _chunk(SAC_TITLE, "The policy maximizes expected return plus an entropy term.", page=2),
    _chunk(SAC_TITLE, "A replay buffer stores past transitions off-policy.", page=3),
    _chunk(RAMP_TITLE, "Ramp metering reduces highway congestion using RL.", page=1),
]


@patch("agents.orchestrator.rerank_cross_encoder", side_effect=_passthrough_ce)
@patch("agents.orchestrator.mmr_rerank", side_effect=_passthrough_mmr)
class TestExactThreePaperComparisonIsolation(unittest.TestCase):
    """The exact three-paper comparison query from Phase 3 Test 5."""

    def setUp(self):
        invalidate_paper_cache()
        orchestrator._v_manager_override = FakeVManager(THREE_PAPER_CORPUS)

    def tearDown(self):
        orchestrator._v_manager_override = None
        invalidate_paper_cache()

    def _state(self):
        query = (
            f"Compare exactly these three papers: '{DQN_TITLE}', "
            f"'{A3C_TITLE}', and '{SAC_TITLE}'."
        )
        return {
            "request_id": "test-req",
            "question": query,
            "repo_id": "",
            "filters": {},
            "retrieval_mode": "single",
        }

    def test_all_three_requested_papers_present(self, mock_ce, mock_mmr):
        result = orchestrator.retrieve_node(self._state())
        papers = {c["metadata"]["paper_title"] for c in result["retrieved_chunks"]}
        self.assertEqual(papers, {DQN_TITLE, A3C_TITLE, SAC_TITLE})

    def test_ramp_metering_paper_never_appears(self, mock_ce, mock_mmr):
        result = orchestrator.retrieve_node(self._state())
        papers = {c["metadata"]["paper_title"] for c in result["retrieved_chunks"]}
        self.assertNotIn(RAMP_TITLE, papers)


@patch("agents.orchestrator.rerank_cross_encoder", side_effect=_passthrough_ce)
@patch("agents.orchestrator.mmr_rerank", side_effect=_passthrough_mmr)
class TestNoUnrestrictedFallbackWhenAllRequestedPapersStarved(unittest.TestCase):
    """
    If every requested paper's filtered search comes back empty, the old
    code fell through to an unrestricted global search. It must now report
    the papers as missing instead — never substitute an unrelated paper.
    """

    def setUp(self):
        invalidate_paper_cache()
        orchestrator._v_manager_override = FakeVManager(THREE_PAPER_CORPUS, starve_all=True)

    def tearDown(self):
        orchestrator._v_manager_override = None
        invalidate_paper_cache()

    def test_multi_paper_all_starved_returns_empty_not_unrestricted_fallback(self, mock_ce, mock_mmr):
        query = f"Compare '{DQN_TITLE}', '{A3C_TITLE}', and '{SAC_TITLE}'."
        state = {
            "request_id": "test-req",
            "question": query,
            "repo_id": "",
            "filters": {},
            "retrieval_mode": "single",
        }
        result = orchestrator.retrieve_node(state)
        self.assertEqual(result["retrieved_chunks"], [])
        self.assertEqual(result.get("error"), "Zero chunks retrieved")

    def test_single_paper_starved_returns_empty_not_unrestricted_fallback(self, mock_ce, mock_mmr):
        state = {
            "request_id": "test-req",
            "question": f"In the paper '{DQN_TITLE}', explain the preprocessing pipeline.",
            "repo_id": "",
            "filters": {},
            "retrieval_mode": "single",
        }
        result = orchestrator.retrieve_node(state)
        # Must be empty/missing, never backfilled with an unrelated paper's chunks.
        self.assertEqual(result["retrieved_chunks"], [])


class TestEnforcePaperIsolationHardFilter(unittest.TestCase):
    """Unit tests for the defense-in-depth _enforce_paper_isolation helper."""

    def test_drops_chunks_not_in_requested_set(self):
        chunks = [
            _chunk(DQN_TITLE, "on-topic"),
            _chunk(RAMP_TITLE, "off-topic"),
        ]
        kept, dropped = _enforce_paper_isolation(chunks, [DQN_TITLE])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["metadata"]["paper_title"], DQN_TITLE)
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["metadata"]["paper_title"], RAMP_TITLE)

    def test_keeps_all_chunks_from_multiple_requested_papers(self):
        chunks = [_chunk(DQN_TITLE, "a"), _chunk(SAC_TITLE, "b")]
        kept, dropped = _enforce_paper_isolation(chunks, [DQN_TITLE, SAC_TITLE])
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, [])

    def test_no_requested_titles_is_a_no_op(self):
        chunks = [_chunk(DQN_TITLE, "a")]
        kept, dropped = _enforce_paper_isolation(chunks, [])
        self.assertEqual(kept, chunks)
        self.assertEqual(dropped, [])


if __name__ == "__main__":
    unittest.main()
