"""
eval.benchmark.systems.codegraphrag
=====================================
Full CodeGraphRAG system adapter.

Wraps the existing orchestrator.answer() pipeline:
  Route → Retrieve (vector + KG + MMR + cross-encoder) → Agent

Research mapping:
  RQ1 (primary system), RQ4 (routing behavior), RQ6 (full pipeline latency).
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Any, List

from eval.benchmark.interface import RetrievedChunk, SystemResponse
from eval.benchmark.systems._base import BaseSystem

# Ensure project root is on path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class CodeGraphRAGSystem(BaseSystem):
    """
    Full CodeGraphRAG system: AST chunking + KG + MMR + cross-encoder + routing.

    This is the primary system under evaluation. All other systems are ablations
    or alternative baselines compared against this.
    """

    @property
    def name(self) -> str:
        return "CodeGraphRAG"

    def warm_up(self) -> None:
        """Pre-load orchestrator pipeline to exclude model loading time from eval."""
        from agents.orchestrator import answer as orchestrator_answer
        # Run one dummy query to warm model caches
        try:
            orchestrator_answer("warm up query")
        except Exception:
            pass  # Warm-up failures are non-fatal

    def _ensure_managers(self):
        """Lazily initialize VectorStoreManager and KnowledgeGraphManager once."""
        if not hasattr(self, "_v_manager"):
            from storage.vector_store import VectorStoreManager
            from storage.knowledge_graph import KnowledgeGraphManager
            self._v_manager = VectorStoreManager()
            self._kg_manager = KnowledgeGraphManager()
            kg_path = os.path.join(_PROJECT_ROOT, "knowledge_graph.json")
            if os.path.exists(kg_path):
                self._kg_manager.load_from_json(kg_path)

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        """
        Run the full retrieval pipeline and return top-k chunks.
        Does NOT run the LLM generation step.
        """
        from retrieval.vector_search import search_vector
        from retrieval.graph_search import expand_by_graph
        from retrieval.metadata_filter import filter_chunks
        from retrieval.mmr_rerank import mmr_rerank
        from retrieval.cross_encoder_rerank import rerank_cross_encoder

        self._ensure_managers()
        retrieval_conf = self.config.get("retrieval", {})
        vector_top_k = retrieval_conf.get("vector_top_k", 30)
        rerank_top_k = retrieval_conf.get("rerank_top_k", 5)

        v_manager = self._v_manager
        kg_manager = self._kg_manager

        chunks = v_manager.search(question, top_k=vector_top_k)

        if retrieval_conf.get("use_graph", True) and chunks:
            all_chunks = v_manager.get_all_chunks()
            chunks = expand_by_graph(chunks, kg_manager, all_chunks=all_chunks, max_expansion=15)

        chunks = filter_chunks(chunks, {})

        if retrieval_conf.get("use_mmr", True) and chunks:
            chunks = mmr_rerank(question, chunks, top_k=min(15, len(chunks)))

        if chunks:
            chunks = rerank_cross_encoder(question, chunks, top_k=top_k)

        return self._normalize_chunks(chunks)

    def answer(self, question: str) -> SystemResponse:
        """Run the full pipeline including LLM generation."""
        from agents.orchestrator import app, AgentState

        initial_state: AgentState = {
            "question": question,
            "agent": "",
            "retrieved_chunks": [],
            "answer": "",
            "error": "",
        }

        error_msg = None
        try:
            final_state = app.invoke(initial_state)
            answer_text = final_state.get("answer", "")
            agent_name = final_state.get("agent", "")
            raw_chunks = final_state.get("retrieved_chunks", [])
        except Exception as e:
            answer_text = ""
            agent_name = "error"
            raw_chunks = []
            error_msg = str(e)

        chunks = self._normalize_chunks(raw_chunks)

        return SystemResponse(
            question=question,
            answer=answer_text,
            retrieved_chunks=chunks,
            agent=agent_name,
            config_snapshot=self.configuration(),
            error=error_msg,
            system_name=self.name,
        )

    def configuration(self) -> Dict[str, Any]:
        base = super().configuration()
        base["system"] = "CodeGraphRAG"
        base["use_kg"] = self.config.get("retrieval", {}).get("use_graph", True)
        base["use_mmr"] = self.config.get("retrieval", {}).get("use_mmr", True)
        base["use_ast"] = True  # full system always uses AST chunking
        base["routing"] = True
        return base
