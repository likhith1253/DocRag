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

app = FastAPI(
    title="DocumentRAG API",
    description="Local research paper question-answering system.",
    version="2.0.0",
)

app.include_router(repository_router)


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class QueryPayload(BaseModel):
    question: str
    collection_id: str = None   # alias for repo_id — both accepted
    repo_id: str = None         # legacy name kept for compatibility
    filters: dict = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "system": "DocumentRAG"}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

@app.post("/query")
def query(payload: QueryPayload):
    question = payload.question
    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Accept either collection_id or repo_id
    repo_id = payload.collection_id or payload.repo_id

    from storage.registry import RepositoryRegistry
    from api.dependencies import registry_instance
    if repo_id and not registry_instance.get_repository(repo_id):
        raise HTTPException(status_code=404, detail=f"Collection '{repo_id}' not found.")

    try:
        ans, latency_breakdown = orchestrator.answer(
            question,
            repo_id=repo_id,
            filters=payload.filters,
        )

        # Read last log entry to extract metadata
        log_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs", "query_logs.jsonl"
        )
        agent = "doc_agent"
        latency = 0.0
        sources: list = []
        citations: list = []
        chunks: list = []

        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    if last_entry.get("question") == question:
                        agent = last_entry.get("agent", "doc_agent")
                        latency = last_entry.get("latency", 0.0)
                        citations = last_entry.get("citations", [])
                        seen_files: set = set()
                        for c in last_entry.get("retrieved_chunks", []):
                            fp = c.get("metadata", {}).get("file")
                            if fp and fp not in seen_files:
                                sources.append(fp)
                                seen_files.add(fp)
                        chunks = last_entry.get("retrieved_chunks", [])
            except Exception:
                pass

        return {
            "answer": ans,
            "agent": agent,
            "latency": latency,
            "latency_breakdown": latency_breakdown,
            "sources": sources,
            "citations": citations,
            "chunks": chunks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


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
