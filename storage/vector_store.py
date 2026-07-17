import os
import yaml
import uuid
import threading
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
# SentenceTransformer and QdrantClient are expensive to initialize (8+ seconds
# each on CPU). Constructing them once per process and reusing them is a safe
# engineering optimization: it does NOT change embeddings, rankings, metrics,
# or any experimental result.  It only eliminates repeated model loading.
# ---------------------------------------------------------------------------
_encoder_cache: Dict[str, SentenceTransformer] = {}
_config_cache: Dict[str, Any] = {}
_ensured_collections = set()
_encoder_lock = threading.Lock()


def _get_config() -> Dict[str, Any]:
    """Load config.yaml once per process."""
    global _config_cache
    if not _config_cache:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def _get_encoder(model_name: str, device: str = "auto") -> SentenceTransformer:
    """Return a cached SentenceTransformer, creating it only on first use."""
    global _encoder_cache
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    key = f"{model_name}::{device}"
    if key not in _encoder_cache:
        _encoder_cache[key] = SentenceTransformer(model_name, device=device)
    return _encoder_cache[key]


class VectorStoreManager:
    _clients = {}
    _all_chunks_cache = {}

    def __init__(self, collection_name: str = "chunks"):
        self.config = _get_config()

        self.qdrant_path = self.config.get("qdrant_path", "./qdrant_storage")
        self.embedding_model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        self.device = self.config.get("device", "auto")
        if self.device == "auto":
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"

        if self.qdrant_path not in VectorStoreManager._clients:
            VectorStoreManager._clients[self.qdrant_path] = QdrantClient(path=self.qdrant_path)
        self.client = VectorStoreManager._clients[self.qdrant_path]

        self.encoder = _get_encoder(self.embedding_model_name, self.device)
        self.collection_name = collection_name

        if hasattr(self.encoder, "get_embedding_dimension"):
            self.vector_size = self.encoder.get_embedding_dimension()
        else:
            self.vector_size = self.encoder.get_sentence_embedding_dimension()
        self._ensure_collection()

    def _ensure_collection(self):
        cache_key = f"{self.qdrant_path}::{self.collection_name}"
        global _ensured_collections
        if cache_key in _ensured_collections:
            return

        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
        except Exception:
            exists = False

        if exists:
            try:
                info = self.client.get_collection(self.collection_name)
                existing_size = info.config.params.vectors.size
                print(f"[Qdrant] Collection '{self.collection_name}' exists. Size: {existing_size}, Expected: {self.vector_size}")
                if existing_size != self.vector_size:
                    print(f"[Qdrant] Size mismatch for '{self.collection_name}'! Deleting and re-creating.")
                    self.client.delete_collection(self.collection_name)
                    exists = False
            except Exception as e:
                print(f"[Qdrant] Error checking collection size for '{self.collection_name}': {e}")

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )
        _ensured_collections.add(cache_key)

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Add chunks to Qdrant collection.
        Each chunk is {"content": str, "metadata": dict}
        """
        if not chunks:
            return

        texts = [c["content"] for c in chunks]

        if "e5" in self.embedding_model_name.lower():
            texts = [f"passage: {t}" for t in texts]

        # Use EmbeddingCache to reuse pre-computed embeddings
        from storage.cache import EmbeddingCache
        cache = EmbeddingCache()
        
        chunk_hashes = [c["metadata"]["hash"] for c in chunks]
        cached_embeddings = cache.get_embeddings(chunk_hashes, self.embedding_model_name)
        
        embeddings = [None] * len(chunks)
        missing_indices = []
        missing_texts = []
        
        for idx, chunk in enumerate(chunks):
            chash = chunk["metadata"]["hash"]
            if chash in cached_embeddings:
                embeddings[idx] = cached_embeddings[chash]
            else:
                missing_indices.append(idx)
                missing_texts.append(texts[idx])
                
        if missing_texts:
            self._update_progress_heartbeat()
            # Acquire lock in a loop, updating heartbeat while waiting to prevent timeouts
            acquired = False
            while not acquired:
                acquired = _encoder_lock.acquire(timeout=5.0)
                self._update_progress_heartbeat()
            try:
                encoded_vectors = self.encoder.encode(missing_texts, show_progress_bar=False).tolist()
            finally:
                _encoder_lock.release()
            self._update_progress_heartbeat()
            pairs_to_cache = []
            for idx, vector in zip(missing_indices, encoded_vectors):
                embeddings[idx] = vector
                pairs_to_cache.append((chunks[idx]["metadata"]["hash"], vector))
            cache.set_embeddings(pairs_to_cache, self.embedding_model_name)

        points = []
        for chunk, vector in zip(chunks, embeddings):
            chunk_hash = chunk["metadata"]["hash"]
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_hash))

            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "content": chunk["content"],
                    "metadata": chunk["metadata"]
                }
            ))

        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        # Invalidate cache if new chunks are added
        cache_key = f"{self.qdrant_path}::{self.collection_name}"
        if cache_key in VectorStoreManager._all_chunks_cache:
            del VectorStoreManager._all_chunks_cache[cache_key]

    def _update_progress_heartbeat(self):
        try:
            if self.collection_name.startswith("collection_"):
                repo_id = self.collection_name.replace("collection_", "")
                from storage.progress import ProgressRegistry
                ProgressRegistry.get_tracker(repo_id).update_heartbeat()
        except Exception:
            pass



    def delete_chunks(self, chunk_hashes: List[str]):
        """
        Delete chunks from Qdrant by computing their UUID5 from the chunk hash.
        """
        if not chunk_hashes:
            return
            
        point_ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, chash)) for chash in chunk_hashes]
        
        from qdrant_client.models import PointIdsList
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=point_ids)
        )
        
        cache_key = f"{self.qdrant_path}::{self.collection_name}"
        if cache_key in VectorStoreManager._all_chunks_cache:
            del VectorStoreManager._all_chunks_cache[cache_key]

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        """Retrieve all chunks from Qdrant, using memory cache to avoid repeated DB scans."""
        cache_key = f"{self.qdrant_path}::{self.collection_name}"
        if cache_key in VectorStoreManager._all_chunks_cache:
            return VectorStoreManager._all_chunks_cache[cache_key]
            
        all_chunks = []
        try:
            scroll_res = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True
            )
            all_chunks = [
                {"content": p.payload["content"], "metadata": p.payload["metadata"]}
                for p in scroll_res[0]
            ]
            VectorStoreManager._all_chunks_cache[cache_key] = all_chunks
        except Exception as e:
            print(f"[Qdrant] Error fetching all chunks: {e}")
            
        return all_chunks

    def search(self, query: str, top_k: int = 30, metadata_filters: Dict[str, Any] = None) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Search for top_k similar chunks with optional metadata filtering.
        Returns (results, timing_dict) where timing_dict has "embedding_ms" and "qdrant_ms".
        """
        import time
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        if "e5" in self.embedding_model_name.lower():
            query_for_encode = f"query: {query}"
        else:
            query_for_encode = query

        t_embed_start = time.perf_counter()
        # Store numpy array so callers (e.g. MMR) can reuse it without re-encoding
        query_vector_np = self.encoder.encode(query_for_encode, show_progress_bar=False)
        query_vector = query_vector_np.tolist()
        t_embed_end = time.perf_counter()
        
        t_qdrant_start = time.perf_counter()
        query_filter = None
        if metadata_filters:
            conditions = []
            for key, val in metadata_filters.items():
                conditions.append(
                    FieldCondition(
                        key=f"metadata.{key}", 
                        match=MatchValue(value=val)
                    )
                )
            query_filter = Filter(must=conditions)

        # with_vectors=True: return stored embeddings so MMR can skip re-encoding
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_vectors=True
        )
        t_qdrant_end = time.perf_counter()
        
        retrieved = []
        for point in results.points:
            entry = {
                "content": point.payload["content"],
                "metadata": point.payload["metadata"],
                "score": point.score,
                "id": point.id
            }
            # Attach stored vector for MMR reuse (avoids re-encoding at query time)
            pv = point.vector
            if isinstance(pv, list) and pv:
                entry["vector"] = pv
            elif isinstance(pv, dict):
                # Named-vector collections: grab the first (default) vector
                first = next(iter(pv.values()), None)
                if first:
                    entry["vector"] = first
            retrieved.append(entry)

        timing = {
            "embedding_ms": (t_embed_end - t_embed_start) * 1000,
            "qdrant_ms": (t_qdrant_end - t_qdrant_start) * 1000,
            # Pass numpy query vector so orchestrator can forward it to MMR
            "query_vector": query_vector_np,
        }
        return retrieved, timing
