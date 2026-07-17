"""
eval.benchmark.systems.single_agent
=======================================
Ablation: No routing — all queries go directly to reasoning_agent.

Ablates: The router component.
Research mapping: RQ4 — does multi-agent routing improve answer quality?
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


class SingleAgentSystem(BaseSystem):
    """Full retrieval pipeline but with routing disabled — always uses reasoning_agent."""

    def __init__(self, config_overrides=None):
        super().__init__(config_overrides)
        # Initialize once at construction time, not per-query
        from storage.vector_store import VectorStoreManager
        from storage.knowledge_graph import KnowledgeGraphManager
        self._v_manager = VectorStoreManager()
        self._kg_manager = KnowledgeGraphManager()
        kg_path = os.path.join(_PROJECT_ROOT, "knowledge_graph.json")
        if os.path.exists(kg_path):
            self._kg_manager.load_from_json(kg_path)

    @property
    def name(self) -> str:
        return "SingleAgent"

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        """Same retrieval as CodeGraphRAG (full pipeline)."""
        from retrieval.graph_search import expand_by_graph
        from retrieval.metadata_filter import filter_chunks
        from retrieval.mmr_rerank import mmr_rerank
        from retrieval.cross_encoder_rerank import rerank_cross_encoder

        retrieval_conf = self.config.get("retrieval", {})
        vector_top_k = retrieval_conf.get("vector_top_k", 30)

        v_manager = self._v_manager
        kg_manager = self._kg_manager

        chunks = v_manager.search(question, top_k=vector_top_k)
        if retrieval_conf.get("use_graph", True) and chunks:
            try:
                scroll_res = v_manager.client.scroll(
                    collection_name=v_manager.collection_name, limit=2000, with_payload=True
                )
                all_chunks = [{"content": p.payload["content"], "metadata": p.payload["metadata"]}
                              for p in scroll_res[0]]
            except Exception:
                all_chunks = []
            chunks = expand_by_graph(chunks, kg_manager, all_chunks=all_chunks, max_expansion=15)

        chunks = filter_chunks(chunks, {})
        if chunks:
            chunks = mmr_rerank(question, chunks, top_k=min(15, len(chunks)))
        if chunks:
            chunks = rerank_cross_encoder(question, chunks, top_k=top_k)
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
            agent="reasoning_agent",  # always reasoning_agent
            config_snapshot=self.configuration(),
            error=error, system_name=self.name,
        )

    def configuration(self) -> Dict[str, Any]:
        base = super().configuration()
        base.update({"system": "SingleAgent", "use_kg": True, "use_mmr": True,
                     "use_reranker": True, "routing": False, "use_ast": True,
                     "forced_agent": "reasoning_agent"})
        return base
