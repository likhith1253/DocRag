"""
eval.benchmark.systems.no_kg
================================
Ablation: Full pipeline minus knowledge graph expansion.

Ablates: expand_by_graph() step only. Everything else (vector, MMR, cross-encoder, routing) unchanged.
Research mapping: RQ2 — does KG independently improve retrieval?
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


class NoKGSystem(BaseSystem):
    """Full pipeline with KG graph expansion disabled."""

    def __init__(self, config_overrides=None):
        super().__init__(config_overrides)
        from storage.vector_store import VectorStoreManager
        self._v_manager = VectorStoreManager()

    @property
    def name(self) -> str:
        return "NoKG"

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        from retrieval.metadata_filter import filter_chunks
        from retrieval.mmr_rerank import mmr_rerank
        from retrieval.cross_encoder_rerank import rerank_cross_encoder

        retrieval_conf = self.config.get("retrieval", {})
        vector_top_k = retrieval_conf.get("vector_top_k", 30)

        chunks = self._v_manager.search(question, top_k=vector_top_k)
        # KG expansion intentionally SKIPPED
        chunks = filter_chunks(chunks, {})
        if chunks:
            chunks = mmr_rerank(question, chunks, top_k=min(15, len(chunks)))
        if chunks:
            chunks = rerank_cross_encoder(question, chunks, top_k=top_k)
        return self._normalize_chunks(chunks)

    def answer(self, question: str) -> SystemResponse:
        from agents.router import route
        from agents import code_agent, data_agent, reasoning_agent

        chunks = self.retrieve(question, top_k=self.config.get("retrieval", {}).get("rerank_top_k", 5))
        raw_chunks = [{"content": c.content, "metadata": c.metadata, "score": c.score} for c in chunks]
        try:
            agent_name, _ = route(question)
            if agent_name == "code_agent":
                answer_text = code_agent.run(question, raw_chunks)
            elif agent_name == "data_agent":
                answer_text = data_agent.run(question, raw_chunks)
            else:
                answer_text = reasoning_agent.run(question, raw_chunks)
            error = None
        except Exception as e:
            answer_text = ""
            agent_name = "error"
            error = str(e)
        return SystemResponse(
            question=question, answer=answer_text, retrieved_chunks=chunks,
            agent=agent_name, config_snapshot=self.configuration(),
            error=error, system_name=self.name,
        )

    def configuration(self) -> Dict[str, Any]:
        base = super().configuration()
        base.update({"system": "NoKG", "use_kg": False, "use_mmr": True,
                     "use_reranker": True, "routing": True, "use_ast": True})
        return base
