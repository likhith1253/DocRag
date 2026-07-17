"""
eval.benchmark.systems.simple_rag
=====================================
Baseline 1: Simple RAG — sliding window chunks + vector search top-K + single LLM call.

No AST, no graph, no MMR, no cross-encoder, no routing.
The most naive RAG baseline. Uses the same no-AST sliding window index as NoASTSystem.

Research mapping: RQ1 — primary comparison baseline.
"""
from __future__ import annotations
import os, sys
from typing import Dict, Any, List

from eval.benchmark.interface import RetrievedChunk, SystemResponse
from eval.benchmark.systems._base import BaseSystem
from eval.benchmark.systems.no_ast import NO_AST_COLLECTION, NO_AST_QDRANT_PATH

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class SimpleRAGSystem(BaseSystem):
    """
    Simple RAG: sliding window chunking, vector search only, single reasoning agent.

    This is the weakest meaningful baseline — establishes the floor performance.
    Uses the same sliding-window index as NoASTSystem to ensure fair comparison.
    """

    @property
    def name(self) -> str:
        return "SimpleRAG"

    def warm_up(self) -> None:
        """Ensure the no-AST index exists (reuses NoASTSystem's build logic).
        Also pre-initialize the singleton encoder so it is warm before evaluation.
        """
        from eval.benchmark.systems.no_ast import NoASTSystem
        helper = NoASTSystem(config_overrides=self.config_overrides)
        helper.warm_up()
        # Pre-load encoder into the module-level singleton cache
        self._get_client_and_encoder()

    def _get_client_and_encoder(self):
        """
        Return a cached (QdrantClient, encoder) pair for the no-AST index.
        Initializes on first call per process; subsequent calls are instant.
        """
        from qdrant_client import QdrantClient
        from storage.vector_store import _get_encoder, _get_config, VectorStoreManager
        
        if NO_AST_QDRANT_PATH not in VectorStoreManager._clients:
            VectorStoreManager._clients[NO_AST_QDRANT_PATH] = QdrantClient(path=NO_AST_QDRANT_PATH)

        cfg = _get_config()
        embedding_model = cfg.get("embedding_model", "intfloat/e5-base-v2")
        device = cfg.get("device", "cpu")
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        encoder = _get_encoder(embedding_model, device)
        client = VectorStoreManager._clients[NO_AST_QDRANT_PATH]
        return client, encoder, embedding_model

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        client, encoder, embedding_model = self._get_client_and_encoder()

        if "e5" in embedding_model.lower():
            query_str = f"query: {question}"
        else:
            query_str = question

        query_vector = encoder.encode(query_str, show_progress_bar=False).tolist()
        results = client.query_points(
            collection_name=NO_AST_COLLECTION,
            query=query_vector,
            limit=top_k,
        )
        chunks = [
            {"content": p.payload["content"], "metadata": p.payload["metadata"], "score": p.score}
            for p in results.points
        ]
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
        base.update({"system": "SimpleRAG", "use_kg": False, "use_mmr": False,
                     "use_reranker": False, "routing": False, "use_ast": False,
                     "chunking_strategy": "sliding_window"})
        return base
