import os
import json
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
        ans = orchestrator.answer(question, repo_id=payload.repo_id, filters=payload.filters)
        
        # Read last log entry to extract metadata
        log_path = "./logs/query_logs.jsonl"
        agent = "unknown"
        latency = 0.0
        sources = []
        
        chunks = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    if last_entry.get("question") == question:
                        agent = last_entry.get("agent", "unknown")
                        latency = last_entry.get("latency", 0.0)
                        # Extract source files and chunks
                        seen_files = set()
                        for c in last_entry.get("retrieved_chunks", []):
                            file_path = c.get("metadata", {}).get("file")
                            if file_path and file_path not in seen_files:
                                sources.append(file_path)
                                seen_files.add(file_path)
                        chunks = last_entry.get("retrieved_chunks", [])
            except Exception:
                pass
                
        return {
            "answer": ans,
            "agent": agent,
            "latency": latency,
            "sources": sources,
            "chunks": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
