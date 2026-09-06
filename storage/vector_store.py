import os
import sys
import time
import yaml
import uuid
import threading

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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


def _resolve_storage_path(path_value: str) -> str:
    """
    Resolve a storage path against the repository root so local Qdrant access
    stays stable regardless of the process working directory.
    """
    if not path_value:
        return path_value
    if os.path.isabs(path_value):
        return path_value
    return os.path.abspath(os.path.join(PROJECT_ROOT, path_value))


def _get_config() -> Dict[str, Any]:
    """Load config.yaml once per process."""
    global _config_cache
    if not _config_cache:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def _get_embedding_device(config: Dict[str, Any] = None) -> str:
    """
    Determine the execution device for SentenceTransformer embeddings.
    Precedence:
    1. config['embedding']['device'] if set
    2. config['device'] if set
    3. Default to 'cpu'
    Resolves 'auto' to 'cuda' (if torch.cuda.is_available()) or 'cpu'.
    """
    if config is None:
        config = _get_config()
    device = None
    emb_cfg = config.get("embedding")
    if isinstance(emb_cfg, dict):
        device = emb_cfg.get("device")
    if not device:
        device = config.get("device")
    if not device:
        device = "cpu"

    device = str(device).lower()
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    return device


def _load_sentence_transformer(model_name: str, device: str) -> SentenceTransformer:
    """
    Safely load SentenceTransformer without creating meta tensors via accelerate/low_cpu_mem_usage.
    """
    try:
        return SentenceTransformer(model_name, device=device, model_kwargs={"low_cpu_mem_usage": False})
    except TypeError:
        pass

    try:
        from sentence_transformers import models
        word_embedding_model = models.Transformer(model_name, model_args={"low_cpu_mem_usage": False})
        pooling_model = models.Pooling(word_embedding_model.get_word_embedding_dimension())
        return SentenceTransformer(modules=[word_embedding_model, pooling_model], device=device)
    except Exception:
        return SentenceTransformer(model_name, device=device)


def _get_embedding_batch_size(config: Dict[str, Any] = None) -> int:
    """Read config['embedding']['batch_size'], defaulting to 32 (sentence-transformers' own default)."""
    if config is None:
        config = _get_config()
    emb_cfg = config.get("embedding")
    batch_size = emb_cfg.get("batch_size") if isinstance(emb_cfg, dict) else None
    try:
        return max(1, int(batch_size))
    except (TypeError, ValueError):
        return 32


def _load_with_gpu_fallback(kind: str, model_name: str, preferred_device: str, loader):
    """
    Load a model via `loader(device)`, preferring CUDA when requested but
    falling back to CPU on ANY failure (CUDA missing, driver error, OOM at
    load time) so a bad/contended GPU environment never crashes the process —
    it just runs slower. Logs which device ended up being used.

    Returns (model, actual_device).
    """
    if preferred_device != "cuda":
        model = loader(preferred_device)
        _log_device_selection(kind, model_name, preferred_device)
        return model, preferred_device

    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False

    if not cuda_available:
        _log_device_selection(kind, model_name, "cpu", reason="CUDA unavailable")
        return loader("cpu"), "cpu"

    try:
        model = loader("cuda")
        _log_device_selection(kind, model_name, "cuda")
        return model, "cuda"
    except Exception as e:
        print(f"[{kind}] CUDA load failed for '{model_name}': {e}. Falling back to CPU.", flush=True)
        _log_device_selection(kind, model_name, "cpu", reason=f"CUDA init/load failed: {e}")
        return loader("cpu"), "cpu"


def _log_device_selection(kind: str, model_name: str, device: str, reason: str = None):
    print(f"{kind} device: {device}", flush=True)
    print(f"{kind} model: {model_name}", flush=True)
    if device == "cuda":
        try:
            import torch
            print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)
        except Exception:
            pass
    elif reason:
        print(f"Reason: {reason}", flush=True)


def _get_encoder(model_name: str, device: str = None) -> SentenceTransformer:
    """Return a cached SentenceTransformer, creating it only on first use."""
    global _encoder_cache
    if device is None:
        device = _get_embedding_device()
    elif device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
    else:
        device = str(device).lower()

    key = f"{model_name}::{device}"
    if key not in _encoder_cache:
        model, actual_device = _load_with_gpu_fallback(
            "Embedding", model_name, device,
            lambda d: _load_sentence_transformer(model_name, d),
        )
        print(f"Embedding batch size: {_get_embedding_batch_size()}", flush=True)
        _encoder_cache[key] = model
        # If we asked for cuda and fell back to cpu, remember that under the
        # "cuda" key too so the next caller (e.g. cross-encoder reranker
        # asking for the same preferred device) doesn't retry a doomed CUDA
        # init on every call.
        if actual_device != device:
            _encoder_cache[f"{model_name}::{actual_device}"] = model
    return _encoder_cache[key]


class VectorStoreManager:
    _clients = {}
    _all_chunks_cache = {}

    def __init__(self, collection_name: str = "chunks"):
        self.config = _get_config()

        self.qdrant_path = _resolve_storage_path(self.config.get("qdrant_path", "./qdrant_storage"))
        self.embedding_model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        self.device = _get_embedding_device(self.config)

        import threading
        if not hasattr(VectorStoreManager, "_client_lock"):
            VectorStoreManager._client_lock = threading.Lock()

        with VectorStoreManager._client_lock:
            if self.qdrant_path not in VectorStoreManager._clients or VectorStoreManager._clients[self.qdrant_path] is None:
                client_obj = None
                max_attempts = 10
                for attempt in range(max_attempts):
                    try:
                        client_obj = QdrantClient(path=self.qdrant_path)
                        break
                    except Exception as e:
                        err_msg = str(e)
                        is_lock_err = (
                            "already accessed by another instance" in err_msg
                            or "AlreadyLocked" in err_msg
                             or "PermissionError" in err_msg
                            or "[Errno 13]" in err_msg
                        )
                        if is_lock_err:
                            qdrant_url = os.environ.get("QDRANT_URL") or self.config.get("qdrant_url")
                            if qdrant_url:
                                client_obj = QdrantClient(url=qdrant_url)
                                break
                            if attempt < max_attempts - 1:
                                time.sleep(0.5 * (attempt + 1))
                            else:
                                raise e
                        else:
                            raise e
                VectorStoreManager._clients[self.qdrant_path] = client_obj
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
                if existing_size != self.vector_size:
                    print(
                        f"[Qdrant] Dimension mismatch for '{self.collection_name}': existing {existing_size} != expected {self.vector_size}. Re-creating collection...",
                        flush=True,
                    )
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

    def drop_collection(self):
        """
        Delete this collection from Qdrant and invalidate the process-wide
        "already ensured" cache for it. Deleting via the raw Qdrant client
        alone leaves _ensured_collections stale, so a later VectorStoreManager
        for the same (qdrant_path, collection_name) would skip recreating it
        in _ensure_collection() and fail with "Collection not found".
        """
        try:
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(collection_name=self.collection_name)
        finally:
            cache_key = f"{self.qdrant_path}::{self.collection_name}"
            _ensured_collections.discard(cache_key)
            VectorStoreManager._all_chunks_cache.pop(cache_key, None)

    def count(self) -> int:
        """Returns total number of vector points stored in this collection."""
        try:
            return self.client.get_collection(self.collection_name).points_count
        except Exception:
            return 0

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
                encoded_vectors = self.encoder.encode(
                    missing_texts, show_progress_bar=False,
                    batch_size=_get_embedding_batch_size(self.config),
                ).tolist()
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



    def verify_points_exist(self, chunk_hashes: List[str]) -> tuple[int, List[str]]:
        """
        Confirm that points for the given chunk hashes are actually present in
        Qdrant, rather than trusting that a prior upsert call succeeded.

        Returns (found_count, missing_hashes).
        """
        unique_hashes = list(dict.fromkeys(chunk_hashes))
        if not unique_hashes:
            return 0, []

        hash_by_point_id = {
            str(uuid.uuid5(uuid.NAMESPACE_DNS, h)): h for h in unique_hashes
        }

        found_point_ids = set()
        point_ids = list(hash_by_point_id.keys())
        retrieve_batch_size = 500
        for i in range(0, len(point_ids), retrieve_batch_size):
            batch_ids = point_ids[i:i + retrieve_batch_size]
            records = self.client.retrieve(
                collection_name=self.collection_name,
                ids=batch_ids,
                with_payload=False,
                with_vectors=False,
            )
            found_point_ids.update(str(r.id) for r in records)

        missing_hashes = [
            h for pid, h in hash_by_point_id.items() if pid not in found_point_ids
        ]
        return len(found_point_ids), missing_hashes

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

    def search(self, query: str, top_k: int = 30, metadata_filters: Dict[str, Any] = None, request_id: str = "default") -> tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Search for top_k similar chunks with optional metadata filtering.
        Returns (results, timing_dict) where timing_dict has "embedding_ms" and "qdrant_ms".
        """
        import time
        import numpy as np
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        from storage.pipeline_logger import log_stage
        
        if "e5" in self.embedding_model_name.lower():
            query_for_encode = f"query: {query}"
        else:
            query_for_encode = query

        t_embed_start = time.perf_counter()
        # Store numpy array so callers (e.g. MMR) can reuse it without re-encoding
        query_vector_np = self.encoder.encode(query_for_encode, show_progress_bar=False)
        query_vector = query_vector_np.tolist()
        t_embed_end = time.perf_counter()
        
        embed_time_ms = (t_embed_end - t_embed_start) * 1000
        vector_norm = float(np.linalg.norm(query_vector_np))
        vector_preview = [round(float(x), 6) for x in query_vector_np[:5]]

        # Stage 2: EMBEDDING logging
        stage2_data = {
            "embedding_model": self.embedding_model_name,
            "embedding_dimension": self.vector_size,
            "latency_ms": round(embed_time_ms, 2),
            "vector_norm": round(vector_norm, 6),
            "vector_preview": vector_preview
        }
        log_stage(request_id, 2, "Embedding", stage2_data, latency_ms=embed_time_ms)

        t_qdrant_start = time.perf_counter()
        query_filter = None
        if metadata_filters:
            conditions = []
            for key, val in metadata_filters.items():
                if key in ("paper_title", "file"):
                    base_val = str(val)
                    if base_val.lower().endswith(".pdf"):
                        base_val = base_val[:-4]
                    pdf_val = f"{base_val}.pdf"
                    conditions.append(
                        Filter(
                            should=[
                                FieldCondition(key="metadata.paper_title", match=MatchValue(value=str(val))),
                                FieldCondition(key="metadata.paper_title", match=MatchValue(value=base_val)),
                                FieldCondition(key="metadata.file", match=MatchValue(value=str(val))),
                                FieldCondition(key="metadata.file", match=MatchValue(value=pdf_val)),
                                FieldCondition(key="metadata.paper", match=MatchValue(value=str(val))),
                            ]
                        )
                    )
                else:
                    conditions.append(
                        FieldCondition(
                            key=f"metadata.{key}", 
                            match=MatchValue(value=val)
                        )
                    )
            query_filter = Filter(must=conditions)

        # with_vectors=True: return stored embeddings so MMR can skip re-encoding
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_vectors=True
            )
        except Exception as qdrant_err:
            import traceback
            tb_str = traceback.format_exc()
            print(f"[VECTOR SEARCH FATAL ERROR] Failed querying collection '{self.collection_name}':\n{tb_str}", flush=True)
            try:
                from storage.pipeline_logger import log_exception
                log_exception(qdrant_err, f"VectorStoreManager.search({self.collection_name})")
            except Exception:
                pass
            raise RuntimeError(
                f"Vector search failed in collection '{self.collection_name}' with filter {metadata_filters}: {qdrant_err}"
            ) from qdrant_err
        t_qdrant_end = time.perf_counter()
        
        retrieved = []
        for point in results.points:
            entry = {
                "content": point.payload["content"],
                "metadata": point.payload["metadata"],
                "score": float(point.score),
                "raw_vector_score": float(point.score),
                "rerank_score": float(point.score),
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
        
        # If metadata_filters were provided but returned zero results, attempt a best-effort
        # normalized filename / paper_title match by querying without filters and post-filtering.
        if not retrieved and metadata_filters:
            try:
                target_val = (
                    metadata_filters.get('file')
                    or metadata_filters.get('paper_title')
                    or metadata_filters.get('paper')
                )
                if target_val:
                    from ntpath import basename
                    def _norm(s):
                        if not s:
                            return ""
                        s = basename(str(s))
                        if s.lower().endswith('.pdf'):
                            s = s[:-4]
                        return s.replace('_', ' ').strip().lower()

                    target_norm = _norm(target_val)
                    raw_results = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=None,
                        limit=top_k,
                        with_vectors=True
                    )
                    for point in raw_results.points:
                        meta = point.payload.get('metadata', {})
                        f_file = meta.get('file') or ''
                        f_title = meta.get('paper_title') or ''
                        f_paper = meta.get('paper') or ''
                        if (target_norm and (
                            _norm(f_file) == target_norm or
                            _norm(f_title) == target_norm or
                            _norm(f_paper) == target_norm
                        )):
                            entry = {
                                "content": point.payload["content"],
                                "metadata": meta,
                                "score": float(point.score),
                                "raw_vector_score": float(point.score),
                                "rerank_score": float(point.score),
                                "id": point.id
                            }
                            pv = point.vector
                            if isinstance(pv, list) and pv:
                                entry["vector"] = pv
                            elif isinstance(pv, dict):
                                first = next(iter(pv.values()), None)
                                if first:
                                    entry["vector"] = first
                            retrieved.append(entry)
            except Exception:
                pass

        qdrant_ms = (t_qdrant_end - t_qdrant_start) * 1000

        # Stage 3: VECTOR SEARCH logging
        retrieved_log = []
        for rank, r in enumerate(retrieved, start=1):
            doc_name = r.get("metadata", {}).get("file") or r.get("metadata", {}).get("paper_title") or "Unknown"
            cid = r.get("id") or r.get("metadata", {}).get("hash") or f"chunk_{rank}"
            sec = r.get("metadata", {}).get("section", "Unknown")
            page = r.get("metadata", {}).get("page_start", "?")
            snippet = r.get("content", "")[:250]
            retrieved_log.append({
                "rank": rank,
                "similarity_score": round(float(r.get("score", 0.0)), 6),
                "chunk_id": str(cid),
                "filename": doc_name,
                "section": sec,
                "page": page,
                "first_250_chars": snippet
            })

        stage3_data = {
            "top_k_requested": top_k,
            "top_k_returned": len(retrieved),
            "collection_name": self.collection_name,
            "qdrant_latency_ms": round(qdrant_ms, 2),
            "retrieved_chunks": retrieved_log
        }
        log_stage(request_id, 3, "Vector Search", stage3_data, latency_ms=qdrant_ms)

        timing = {
            "embedding_ms": embed_time_ms,
            "qdrant_ms": qdrant_ms,
            # Pass numpy query vector so orchestrator can forward it to MMR
            "query_vector": query_vector_np,
        }
        return retrieved, timing
