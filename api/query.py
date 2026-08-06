from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import agents.orchestrator as orchestrator

router = APIRouter(tags=["query"])

from typing import Optional

class QueryPayload(BaseModel):
    question: str
    repo_id: Optional[str] = None
    collection_id: Optional[str] = None
    filters: Optional[dict] = None
    retrieval_mode: Optional[str] = "single"

@router.post("/query")
def query(payload: QueryPayload):
    question = payload.question
    effective_repo_id = payload.repo_id or payload.collection_id
    
    try:
        ans, latency_breakdown, chunks, citations = orchestrator.answer(
            question,
            repo_id=effective_repo_id,
            filters=payload.filters,
            retrieval_mode=payload.retrieval_mode or "single"
        )

        agent = "doc_agent"
        latency = latency_breakdown.get("total_ms", 0.0) / 1000.0

        # Extract source file list from chunks
        seen_files = set()
        sources = []
        for c in chunks:
            file_path = c.get("metadata", {}).get("file")
            if file_path and file_path not in seen_files:
                sources.append(file_path)
                seen_files.add(file_path)

        return {
            "answer": ans,
            "agent": agent,
            "latency": latency,
            "sources": sources,
            "citations": citations,
            "chunks": chunks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
