from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import agents.orchestrator as orchestrator

router = APIRouter(tags=["query"])

class QueryPayload(BaseModel):
    question: str
    repo_id: str = None
    filters: dict = None

@router.post("/query")
def query(payload: QueryPayload):
    question = payload.question
    
    try:
        # BUG FIX: orchestrator.answer() returns a tuple of 4 values:
        #   (answer_text, latency_breakdown, chunks, citations)
        # Previously this was assigned to a single variable `ans`, meaning
        # `ans` was the entire tuple — not the answer string.  This caused
        # garbled or unusable responses from this endpoint.
        ans, latency_breakdown, chunks, citations = orchestrator.answer(
            question, repo_id=payload.repo_id, filters=payload.filters
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
