"""
DocumentRAG FastAPI Application.
Production research paper question-answering API.
Preserves collection/registry infrastructure for collection isolation.

Endpoints:
  GET  /health               — liveness check
  POST /query                — answer a question from an indexed collection
  GET  /indexing/status/{id} — progress polling

  (Collection CRUD is in api/repository.py, mounted at /repository/)
"""

import os
import json
import threading
import time

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from storage.registry import RepositoryRegistry
from api.repository import router as repository_router
from api.dependencies import get_registry

import agents.orchestrator as orchestrator

from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n[STARTUP] Warm-up: Pre-loading LLM backend model in background...", flush=True)
    def _warmup():
        try:
            from llm.backend_factory import get_backend
            backend = get_backend()
            print(
                f"[STARTUP] backend id={id(backend)} class={backend.__class__.__name__} "
                f"model_name={getattr(backend, 'model_name', None)} device={getattr(backend, 'device', None)} "
                f"loaded_before={bool(getattr(backend, 'model', None) is not None and getattr(backend, 'tokenizer', None) is not None)}",
                flush=True,
            )
            if hasattr(backend, "ensure_loaded"):
                backend.ensure_loaded()
            else:
                backend._ensure_loaded()
            print(
                f"[STARTUP] backend id={id(backend)} class={backend.__class__.__name__} "
                f"model_name={getattr(backend, 'model_name', None)} device={getattr(backend, 'device', None)} "
                f"loaded_after={bool(getattr(backend, 'model', None) is not None and getattr(backend, 'tokenizer', None) is not None)}",
                flush=True,
            )
            print("[STARTUP] LLM backend model loaded successfully!", flush=True)
        except Exception as e:
            print(f"[STARTUP WARN] LLM backend pre-load error: {e}", flush=True)

    threading.Thread(target=_warmup, daemon=True).start()
    yield

app = FastAPI(
    title="DocumentRAG API",
    description="Local research paper question-answering system.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repository_router)


def _backend_health_payload():
    try:
        from llm.backend_factory import get_backend

        backend = get_backend()
        loaded = bool(
            getattr(backend, "model", None) is not None and
            getattr(backend, "tokenizer", None) is not None
        )
        backend_object_id = id(backend)
        backend_class = backend.__class__.__name__
        model_name = getattr(backend, "model_name", None)
        device = getattr(backend, "device", None)
        dtype = getattr(backend, "dtype_str", None)
        gpu_name = getattr(backend, "gpu_name", None)
        print(
            f"[HEALTH] backend id={backend_object_id} class={backend_class} "
            f"model_name={model_name} device={device} dtype={dtype} "
            f"gpu_name={gpu_name} model_loaded={loaded}",
            flush=True,
        )
        backend_info = {
            "backend_name": backend_class,
            "backend_class": backend_class,
            "backend_object_id": backend_object_id,
            "model_name": model_name,
            "device": device,
            "dtype": dtype,
            "gpu_name": gpu_name,
            "model_loaded": loaded,
            "loaded": loaded,
        }
        return backend_info
    except Exception as exc:
        return {
            "backend_name": None,
            "backend_class": None,
            "backend_object_id": None,
            "model_name": None,
            "device": None,
            "dtype": None,
            "gpu_name": None,
            "model_loaded": False,
            "loaded": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class QueryPayload(BaseModel):
    question: str
    collection_id: str = None   # alias for repo_id — both accepted
    repo_id: str = None         # legacy name kept for compatibility
    filters: dict = None
    request_id: str = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "system": "DocumentRAG",
        "backend": _backend_health_payload(),
    }


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

@app.post("/query")
def query(payload: QueryPayload):
    req_start = time.perf_counter()
    from storage.pipeline_logger import generate_request_id
    req_id = payload.request_id or generate_request_id()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n==================================================", flush=True)
    print(f"[{now_str}] [REQUEST RECEIVED] (Request ID: {req_id})", flush=True)
    print(f"Question: {payload.question}", flush=True)
    print(f"Collection ID / Repo ID: {payload.collection_id or payload.repo_id}", flush=True)
    print(f"==================================================", flush=True)

    question = payload.question
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Accept either collection_id or repo_id
    repo_id = payload.collection_id or payload.repo_id

    t_lookup_start = time.perf_counter()
    from storage.registry import RepositoryRegistry
    from api.dependencies import registry_instance
    if repo_id and not registry_instance.get_repository(repo_id):
        raise HTTPException(status_code=404, detail=f"Collection '{repo_id}' not found.")
    t_lookup_end = time.perf_counter()

    try:
        t_orch_start = time.perf_counter()
        ans, latency_breakdown, chunks, citations = orchestrator.answer(
            question,
            repo_id=repo_id,
            filters=payload.filters,
            request_id=req_id,
        )
        t_orch_end = time.perf_counter()

        t_meta_start = time.perf_counter()
        agent = "doc_agent"
        latency = (t_orch_end - t_orch_start)
        seen_files: set = set()
        sources: list = []
        for c in chunks:
            fp = c.get("metadata", {}).get("file")
            if fp and fp not in seen_files:
                sources.append(fp)
                seen_files.add(fp)

        response_dict = {
            "request_id": req_id,
            "answer": ans,
            "agent": agent,
            "latency": latency,
            "latency_breakdown": latency_breakdown,
            "sources": sources,
            "citations": citations,
            "chunks": chunks,
        }

        t_ser_start = time.perf_counter()
        _ = json.dumps(response_dict, default=str)
        t_ser_end = time.perf_counter()
        print(f"Response Serialization .......... {(t_ser_end - t_ser_start)*1000:.2f} ms", flush=True)

        req_total_ms = (time.perf_counter() - req_start) * 1000
        print(f"==================================================", flush=True)
        print(f"[REQUEST COMPLETE] Total Time: {req_total_ms/1000:.2f} sec ({req_total_ms:.2f} ms)", flush=True)
        print(f"==================================================\n", flush=True)

        return response_dict
    except Exception as e:
        from storage.pipeline_logger import log_exception
        log_exception(e, "api/main.py::query")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


# ---------------------------------------------------------------------------
# Cache Clearing
# ---------------------------------------------------------------------------

@app.post("/cache/clear")
def clear_all_caches():
    try:
        from storage.cache import SemanticCache
        sem_cache = SemanticCache()
        sem_cache.clear()
    except Exception as e:
        print(f"Error clearing semantic cache: {e}")

    try:
        from storage.cache import EmbeddingCache
        emb_cache = EmbeddingCache()
        emb_cache.clear()
        emb_cache.close()
    except Exception as e:
        print(f"Error clearing embedding cache: {e}")

    try:
        from pathlib import Path
        cache_path = Path("logs/llm_prompt_cache.json")
        if cache_path.exists():
            cache_path.unlink()
    except Exception as e:
        print(f"Error clearing LLM prompt cache: {e}")

    return {"status": "success", "message": "All caches cleared successfully."}


# ---------------------------------------------------------------------------
# Indexing progress
# ---------------------------------------------------------------------------

@app.get("/indexing/status/{repo_id}")
def get_indexing_status(
    repo_id: str, registry: RepositoryRegistry = Depends(get_registry)
):
    from storage.progress import ProgressRegistry

    ProgressRegistry.check_heartbeats(registry)

    tracker = ProgressRegistry.get_tracker(repo_id)
    if tracker.stage == "queued":
        repo = registry.get_repository(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Collection not found")
        if repo.status == "READY":
            tracker.update(status="READY", stage="completed", percentage=100.0)
        elif repo.status == "FAILED":
            tracker.update(status="FAILED", stage="failed", percentage=0.0)

    return tracker.to_dict()


# ---------------------------------------------------------------------------
# Background heartbeat monitor
# ---------------------------------------------------------------------------

def heartbeat_monitor():
    while True:
        try:
            from api.dependencies import registry_instance
            from storage.progress import ProgressRegistry
            ProgressRegistry.check_heartbeats(registry_instance)
        except Exception as e:
            print(f"[Heartbeat] Error: {e}")
        time.sleep(5)


monitor_thread = threading.Thread(target=heartbeat_monitor, daemon=True)
monitor_thread.start()
