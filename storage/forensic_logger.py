"""
forensic_logger.py
-------------------
Production Forensic Diagnostic Logger for DocumentRAG.

Overwrites '.debug/current_query/' on every single request with 7 clean diagnostic files:
  1. summary.txt
  2. lifecycle.txt
  3. retrieval.txt
  4. routing.txt
  5. llm.txt
  6. exceptions.txt
  7. response.json
"""

import os
import sys
import time
import json
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DEBUG_DIR = ROOT_DIR / ".debug" / "current_query"


class ForensicLogger:
    def __init__(self, request_id: str = "default"):
        self.request_id = request_id
        self.start_time = time.perf_counter()
        self.lifecycle_events = []
        self.routing_info = {}
        self.retrieval_info = {}
        self.llm_info = {}
        self.exceptions = []
        self.response_payload = {}
        self.status = "SUCCESS"

    def log_event(self, stage: str, details: str):
        elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        self.lifecycle_events.append(f"[{elapsed_ms:8.2f} ms] {stage.upper():<20} | {details}")

    def set_routing(self, repo_id: str, collection_name: str, points_count: int, filters: dict):
        self.routing_info = {
            "request_id": self.request_id,
            "repo_id": repo_id,
            "collection_name": collection_name,
            "collection_points_count": points_count,
            "filters": filters or {},
        }
        self.log_event("routing", f"repo_id='{repo_id}' -> collection='{collection_name}' ({points_count} points)")

    def set_retrieval(self, vector_top_k: int, retrieved_count: int, mmr_count: int, ce_count: int, chunks: list):
        chunk_details = []
        for c in chunks:
            m = c.get("metadata", {})
            chunk_details.append({
                "id": str(c.get("id") or m.get("hash") or "unknown"),
                "score": float(c.get("score", 0.0)),
                "file": m.get("file") or m.get("paper_title") or "Unknown",
                "section": m.get("section", "Unknown"),
                "pages": f"{m.get('page_start', '?')}–{m.get('page_end', '?')}",
                "content_snippet": str(c.get("content", ""))[:200],
            })
        self.retrieval_info = {
            "vector_top_k": vector_top_k,
            "raw_vector_retrieved": retrieved_count,
            "after_mmr_count": mmr_count,
            "after_cross_encoder_count": ce_count,
            "final_chunks": chunk_details,
        }
        self.log_event("retrieval", f"Raw: {retrieved_count} -> MMR: {mmr_count} -> Rerank: {ce_count}")

    def set_llm(self, prompt_len_chars: int, approx_tokens: int, llm_ms: float, raw_output: str):
        self.llm_info = {
            "prompt_length_chars": prompt_len_chars,
            "approx_tokens": approx_tokens,
            "llm_latency_ms": round(llm_ms, 2),
            "raw_output_snippet": str(raw_output)[:500],
            "raw_output_full": raw_output,
        }
        self.log_event("llm", f"Tokens: ~{approx_tokens} | Latency: {llm_ms:.1f} ms")

    def log_exception(self, stage: str, exc: Exception):
        self.status = "FAILED"
        tb = traceback.format_exc()
        self.exceptions.append({
            "stage": stage,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": tb,
        })
        self.log_event("EXCEPTION", f"{stage} -> {exc}")

    def finalize(self, answer: str, citations: list, latency_bd: dict):
        total_ms = (time.perf_counter() - self.start_time) * 1000
        self.response_payload = {
            "request_id": self.request_id,
            "status": self.status,
            "answer": answer,
            "citations_count": len(citations or []),
            "citations": citations or [],
            "latency_breakdown_ms": latency_bd or {},
            "total_latency_ms": round(total_ms, 2),
        }

        # Ensure clean target directory
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

        # 1. summary.txt
        summary_txt = [
            f"=== DOCUMENTRAG FORENSIC SUMMARY ===",
            f"Request ID      : {self.request_id}",
            f"Status          : {self.status}",
            f"Total Time      : {total_ms:.2f} ms",
            f"Repo ID         : {self.routing_info.get('repo_id')}",
            f"Collection      : {self.routing_info.get('collection_name')} ({self.routing_info.get('collection_points_count', 0)} points)",
            f"Retrieved Chunks: {len(self.retrieval_info.get('final_chunks', []))}",
            f"Citations Built : {len(self.response_payload.get('citations', []))}",
            f"LLM Latency     : {self.llm_info.get('llm_latency_ms', 0)} ms",
            f"Exceptions      : {len(self.exceptions)}",
        ]
        (DEBUG_DIR / "summary.txt").write_text("\n".join(summary_txt), encoding="utf-8")

        # 2. lifecycle.txt
        (DEBUG_DIR / "lifecycle.txt").write_text("\n".join(self.lifecycle_events), encoding="utf-8")

        # 3. retrieval.txt
        (DEBUG_DIR / "retrieval.txt").write_text(json.dumps(self.retrieval_info, indent=2), encoding="utf-8")

        # 4. routing.txt
        (DEBUG_DIR / "routing.txt").write_text(json.dumps(self.routing_info, indent=2), encoding="utf-8")

        # 5. llm.txt
        (DEBUG_DIR / "llm.txt").write_text(json.dumps(self.llm_info, indent=2), encoding="utf-8")

        # 6. exceptions.txt
        exc_str = "\n\n".join([f"=== STAGE: {e['stage']} ===\n{e['traceback']}" for e in self.exceptions]) if self.exceptions else "NO EXCEPTIONS LOGGED."
        (DEBUG_DIR / "exceptions.txt").write_text(exc_str, encoding="utf-8")

        # 7. response.json
        (DEBUG_DIR / "response.json").write_text(json.dumps(self.response_payload, indent=2), encoding="utf-8")

        print(f"[FORENSIC DEBUG] Successfully wrote 7 diagnostic artifacts to {DEBUG_DIR}", flush=True)
