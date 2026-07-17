"""
eval.benchmark.systems.hybrid
================================
Baseline: Hybrid retrieval — BM25 + Dense vector fusion via Reciprocal Rank Fusion (RRF).

Combines sparse (BM25) and dense (E5) ranks using RRF score = Σ 1/(k + rank_i).
No reranking applied. Generation uses reasoning_agent.

Reviewer note: RRF is a parameter-free fusion method (Cormack et al., 2009).
k=60 is the standard constant. No training required.

Research mapping: RQ7 — does hybrid retrieval outperform both pure sparse and dense?
"""
from __future__ import annotations
import os, sys
from typing import Dict, Any, List, Tuple

from eval.benchmark.interface import RetrievedChunk, SystemResponse
from eval.benchmark.systems._base import BaseSystem

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

RRF_K = 60  # standard constant from Cormack et al., 2009


class HybridSystem(BaseSystem):
    """
    Hybrid BM25 + Dense retrieval via Reciprocal Rank Fusion (RRF).

    Retrieves top-N candidates from both BM25 and Dense independently,
    then fuses their ranked lists using RRF.
    """

    @property
    def name(self) -> str:
        return "Hybrid"

    def warm_up(self) -> None:
        """Build BM25 index (dense index already in Qdrant)."""
        from rank_bm25 import BM25Okapi
        from storage.vector_store import VectorStoreManager

        print("[HybridSystem] Building BM25 index for hybrid retrieval...")
        v_manager = VectorStoreManager()
        self._v_manager = v_manager
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
            print(f"[HybridSystem] Warning: {e}")
            self._all_chunks = []

        if self._all_chunks:
            tokenized_corpus = [c["content"].lower().split() for c in self._all_chunks]
            self._bm25 = BM25Okapi(tokenized_corpus)
            print(f"[HybridSystem] BM25 + Dense ready ({len(self._all_chunks)} chunks)")
        else:
            self._bm25 = None

    def _get_bm25_ranked(self, question: str, n: int) -> List[Tuple[int, float]]:
        """Returns (chunk_idx, score) sorted by BM25 score descending."""
        import numpy as np
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(question.lower().split())
        top_indices = np.argsort(scores)[::-1][:n]
        return [(int(idx), float(scores[idx])) for idx in top_indices]

    def _get_dense_ranked(self, question: str, n: int) -> List[Tuple[str, float]]:
        """Returns (chunk_hash_or_id, score) from dense retrieval."""
        if not hasattr(self, "_v_manager"):
            from storage.vector_store import VectorStoreManager
            self._v_manager = VectorStoreManager()
        results = self._v_manager.search(question, top_k=n)
        return results  # list of {content, metadata, score}

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        if not hasattr(self, "_bm25"):
            self.warm_up()

        n_candidates = self.config.get("retrieval", {}).get("vector_top_k", 30)

        # BM25 ranks
        bm25_ranked = self._get_bm25_ranked(question, n_candidates)
        # Dense ranks
        dense_results = self._get_dense_ranked(question, n_candidates)

        # Build RRF scores
        rrf_scores: Dict[str, float] = {}
        chunk_by_key: Dict[str, dict] = {}

        # Process BM25 results (keyed by chunk content hash)
        import hashlib
        for rank, (idx, score) in enumerate(bm25_ranked):
            chunk = self._all_chunks[idx]
            key = chunk["metadata"].get("hash", hashlib.md5(chunk["content"][:100].encode()).hexdigest())
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)
            chunk_by_key[key] = {**chunk, "score": score}

        # Process dense results
        for rank, result in enumerate(dense_results):
            meta = result.get("metadata", {})
            key = meta.get("hash", hashlib.md5(result.get("content", "")[:100].encode()).hexdigest())
            rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (RRF_K + rank + 1)
            chunk_by_key[key] = {
                "content": result.get("content", ""),
                "metadata": meta,
                "score": result.get("score", 0.0),
            }

        # Sort by RRF score
        sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
        chunks = []
        for key in sorted_keys:
            chunk = dict(chunk_by_key[key])
            chunk["score"] = rrf_scores[key]  # Use RRF score as the final score
            chunks.append(chunk)

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
        base.update({"system": "Hybrid", "retrieval_method": "bm25_plus_dense_rrf",
                     "rrf_k": RRF_K, "use_kg": False, "use_mmr": False,
                     "use_reranker": False, "routing": False})
        return base
