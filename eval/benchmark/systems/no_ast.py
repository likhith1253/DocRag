"""
eval.benchmark.systems.no_ast
================================
Ablation: Sliding window chunking (no AST parsing) + full retrieval pipeline.

Ablates: AST-aware chunking. Uses fixed-size sliding window chunks from the
vector store, but if the store was built with AST chunks, this baseline is
invalid. The correct approach: this system uses a SEPARATELY BUILT index
from sliding-window chunks.

Implementation note:
  Building a separate index for this baseline requires re-ingesting with
  chunking strategy = "sliding_window". This is done on first warm_up() call
  using a separate Qdrant collection "chunks_no_ast" and a separate KG.

Research mapping: RQ3 — does AST chunking independently improve retrieval?
"""
from __future__ import annotations
import os, sys, shutil
from typing import Dict, Any, List

from eval.benchmark.interface import RetrievedChunk, SystemResponse
from eval.benchmark.systems._base import BaseSystem

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

NO_AST_COLLECTION = "chunks_no_ast"
NO_AST_QDRANT_PATH = os.path.join(_PROJECT_ROOT, "qdrant_storage_no_ast")
NO_AST_KG_PATH = os.path.join(_PROJECT_ROOT, "knowledge_graph_no_ast.json")


class NoASTSystem(BaseSystem):
    """
    Full retrieval pipeline but built on sliding-window (non-AST) chunks.

    Uses a separate Qdrant collection and KG built with strategy="sliding_window".
    The warm_up() method builds this index if it does not already exist.
    """

    @property
    def name(self) -> str:
        return "NoAST"

    def warm_up(self) -> None:
        """Build the no-AST index if it does not exist."""
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
        from sentence_transformers import SentenceTransformer
        from storage.vector_store import VectorStoreManager

        if NO_AST_QDRANT_PATH not in VectorStoreManager._clients:
            VectorStoreManager._clients[NO_AST_QDRANT_PATH] = QdrantClient(path=NO_AST_QDRANT_PATH)
        client = VectorStoreManager._clients[NO_AST_QDRANT_PATH]
        try:
            collections = client.get_collections().collections
            exists = any(c.name == NO_AST_COLLECTION for c in collections)
        except Exception:
            exists = False

        if not exists:
            print(f"[NoASTSystem] Building sliding-window index at {NO_AST_QDRANT_PATH} ...")
            self._build_no_ast_index(client)
        else:
            print(f"[NoASTSystem] Index already exists at {NO_AST_QDRANT_PATH}")

    def _build_no_ast_index(self, client) -> None:
        """
        Build a Qdrant collection using sliding-window chunking (no AST).
        Ingests the CodeGraphRAG repository itself.
        """
        import uuid
        from qdrant_client.models import Distance, VectorParams, PointStruct
        from storage.vector_store import _get_encoder
        from ingestion.loader import load_repository
        from ingestion.language_detect import detect_language

        embedding_model = self.config.get("embedding_model", "intfloat/e5-base-v2")
        device = self.config.get("device", "auto")
        encoder = _get_encoder(embedding_model, device)
        vector_size = encoder.get_sentence_embedding_dimension()

        client.create_collection(
            collection_name=NO_AST_COLLECTION,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

        max_tokens = 512
        overlap = 64

        def sliding_window_chunk(file_path: str, content: str, repo_name: str) -> List[Dict]:
            """Simple sliding window chunker — no AST."""
            lines = content.splitlines()
            chunks = []
            i = 0
            chunk_idx = 0
            while i < len(lines):
                chunk_lines = lines[i: i + max_tokens]
                chunk_text = "\n".join(chunk_lines)
                if chunk_text.strip():
                    import hashlib, datetime
                    h = hashlib.md5(f"{file_path}:{i}:{chunk_text}".encode()).hexdigest()
                    chunks.append({
                        "content": chunk_text,
                        "metadata": {
                            "file": file_path,
                            "language": detect_language(file_path),
                            "hash": h,
                            "lines": f"{i+1}-{i+len(chunk_lines)}",
                            "chunking_strategy": "sliding_window",
                        }
                    })
                i += max(1, max_tokens - overlap)
                chunk_idx += 1
            return chunks

        all_chunks = []
        for file_info in load_repository(_PROJECT_ROOT):
            fp = file_info["file_path"]
            if fp.replace("\\", "/").startswith(".venv/") or not fp.endswith((".py", ".md")):
                continue
            chunks = sliding_window_chunk(fp, file_info["content"], file_info["repo_name"])
            all_chunks.extend(chunks)

        print(f"[NoASTSystem] Generated {len(all_chunks)} sliding-window chunks")

        texts = [c["content"] for c in all_chunks]
        embeddings = encoder.encode(texts, show_progress_bar=True, batch_size=32).tolist()

        points = []
        for chunk, vector in zip(all_chunks, embeddings):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["metadata"]["hash"]))
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={"content": chunk["content"], "metadata": chunk["metadata"]}
            ))

        client.upsert(collection_name=NO_AST_COLLECTION, points=points)
        print(f"[NoASTSystem] Indexed {len(points)} chunks")

    _client_cache = {}

    def retrieve(self, question: str, top_k: int = 5) -> List[RetrievedChunk]:
        from qdrant_client import QdrantClient
        from storage.vector_store import _get_encoder
        from retrieval.metadata_filter import filter_chunks
        from retrieval.mmr_rerank import mmr_rerank
        from retrieval.cross_encoder_rerank import rerank_cross_encoder

        embedding_model = self.config.get("embedding_model", "intfloat/e5-base-v2")
        device = self.config.get("device", "auto")
        encoder = _get_encoder(embedding_model, device)

        from storage.vector_store import VectorStoreManager

        if NO_AST_QDRANT_PATH not in VectorStoreManager._clients:
            VectorStoreManager._clients[NO_AST_QDRANT_PATH] = QdrantClient(path=NO_AST_QDRANT_PATH)
        client = VectorStoreManager._clients[NO_AST_QDRANT_PATH]

        query_vector = encoder.encode(question, show_progress_bar=False).tolist()

        retrieval_conf = self.config.get("retrieval", {})
        results = client.query_points(
            collection_name=NO_AST_COLLECTION,
            query=query_vector,
            limit=retrieval_conf.get("vector_top_k", 30),
        )

        chunks = [
            {"content": p.payload["content"], "metadata": p.payload["metadata"], "score": p.score}
            for p in results.points
        ]
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
        base.update({"system": "NoAST", "use_kg": False, "use_mmr": True,
                     "use_reranker": True, "routing": True, "use_ast": False,
                     "chunking_strategy": "sliding_window",
                     "no_ast_collection": NO_AST_COLLECTION})
        return base
