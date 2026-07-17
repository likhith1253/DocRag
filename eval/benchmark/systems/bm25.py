"""
eval.benchmark.systems.bm25
==============================
Baseline: BM25 sparse retrieval.

Uses rank_bm25. Indexes all chunks from the AST-based Qdrant collection at warm_up time.
Generation uses reasoning_agent (same as VectorOnly — generator held fixed for fair comparison).

Reviewer note: BM25 + reasoning_agent vs VectorSearch + reasoning_agent isolates
the retrieval component. The paper will explicitly state this is a retrieval-only comparison.

Research mapping: RQ1 (floor baseline), RQ7 (sparse vs dense).
"""
from __future__ import annotations
import os, sys
from typing import Dict, Any, List

from eval.benchmark.interface import RetrievedChunk, SystemResponse
from eval.benchmark.systems._base import BaseSystem

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class BM25System(BaseSystem):
    """
    BM25 sparse retrieval baseline.

    Indexes all AST-based chunks at warm_up time. Retrieves by BM25 score.
    Generation: reasoning_agent (same LLM as other baselines).
    """

    @property
    def name(self) -> str:
        return "BM25"

    def warm_up(self) -> None:
        """Load all chunks from Qdrant and build BM25 index."""
        from rank_bm25 import BM25Okapi
        from storage.vector_store import VectorStoreManager

        print("[BM25System] Building BM25 index from existing Qdrant chunks...")
        v_manager = VectorStoreManager()
        try:
            scroll_res = v_manager.client.scroll(
                collection_name=v_manager.collection_name,
                limit=5000,
                with_payload=True,
            )
            self._all_chunks = [
                {"content": p.payload["content"], "metadata": p.payload["metadata"]}
                for p in scroll_res[0]
            ]
        except Exception as e:
            print(f"[BM25System] Warning: could not scroll Qdrant: {e}")
            self._all_chunks = []

        if self._all_chunks:
            tokenized_corpus = [chunk["content"].lower().split() for chunk in self._all_chunks]
            self._bm25 = BM25Okapi(tokenized_corpus)
            print(f"[BM25System] BM25 index built on {len(self._all_chunks)} chunks")
        else:
            self._bm25 = None
            print("[BM25System] WARNING: No chunks found. BM25 will return empty results.")

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        if not hasattr(self, "_bm25") or self._bm25 is None:
            self.warm_up()
        if self._bm25 is None:
            return []

        tokenized_query = question.lower().split()
        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k indices
        import numpy as np
        top_indices = np.argsort(scores)[::-1][:top_k]

        chunks = []
        for i, idx in enumerate(top_indices):
            raw_chunk = self._all_chunks[idx]
            chunks.append({
                "content": raw_chunk["content"],
                "metadata": raw_chunk["metadata"],
                "score": float(scores[idx]),
            })

        return self._normalize_chunks(chunks)

    def answer(self, question: str) -> SystemResponse:
        from agents.reasoning_agent import run as reasoning_run

        top_k = self.config.get("retrieval", {}).get("rerank_top_k", 5)
        chunks = self.retrieve(question, top_k=top_k)
        raw_chunks = [{"content": c.content, "metadata": c.metadata, "score": c.score} for c in chunks]
        try:
            answer_text = reasoning_run(question, raw_chunks)
            error = None
        except Exception as e:
            answer_text = ""
            error = str(e)
        return SystemResponse(
            question=question, answer=answer_text, retrieved_chunks=chunks,
            agent="reasoning_agent", config_snapshot=self.configuration(),
            error=error, system_name=self.name,
        )

    def configuration(self) -> Dict[str, Any]:
        base = super().configuration()
        base.update({"system": "BM25", "retrieval_method": "bm25_okapi",
                     "use_kg": False, "use_mmr": False, "use_reranker": False,
                     "routing": False})
        return base
