"""
eval.benchmark.systems.vector_only
=====================================
Baseline: Vector search only, top-K direct, no KG, no MMR, no cross-encoder.

Ablates: KG expansion + reranking (both MMR and cross-encoder).
Research mapping: RQ1 (simplest dense baseline), RQ7 (vs BM25/Hybrid).
"""
from __future__ import annotations
import os
import sys
from typing import Dict, Any, List

from eval.benchmark.interface import RetrievedChunk, SystemResponse
from eval.benchmark.systems._base import BaseSystem

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class VectorOnlySystem(BaseSystem):
    """Vector search top-K, no graph, no MMR, no cross-encoder, no routing."""

    @property
    def name(self) -> str:
        return "VectorOnly"

    def warm_up(self) -> None:
        from storage.vector_store import VectorStoreManager
        self._v_manager = VectorStoreManager()

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        from storage.vector_store import VectorStoreManager
        v_manager = getattr(self, "_v_manager", VectorStoreManager())
        chunks = v_manager.search(question, top_k=top_k)
        return self._normalize_chunks(chunks)

    def answer(self, question: str) -> SystemResponse:
        from agents.reasoning_agent import run as reasoning_run
        chunks = self.retrieve(question, top_k=self.config.get("retrieval", {}).get("rerank_top_k", 5))
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
        base.update({"system": "VectorOnly", "use_kg": False, "use_mmr": False,
                     "use_reranker": False, "routing": False})
        return base
