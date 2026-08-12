import os
import sys
import math

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any
from storage.vector_store import _get_config, _get_embedding_device
from retrieval.query_analyzer import detect_question_type, score_chunk_for_question

_cross_encoder_cache: Dict[str, CrossEncoder] = {}

def _load_cross_encoder(model_name: str, device: str) -> CrossEncoder:
    """
    Safely load CrossEncoder without creating meta tensors via accelerate/low_cpu_mem_usage.
    """
    try:
        return CrossEncoder(model_name, device=device, automodel_args={"low_cpu_mem_usage": False})
    except Exception:
        return CrossEncoder(model_name, device=device)

def rerank_cross_encoder(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 5,
    request_id: str = "default",
) -> List[Dict[str, Any]]:
    """
    Rerank chunks using a Cross-Encoder model with question-type-aware biasing.
    """
    import time
    from storage.pipeline_logger import log_stage
    t_start = time.perf_counter()

    if not chunks:
        stage6_data = {
            "cross_encoder_enabled": True,
            "input_chunks_count": 0,
            "output_chunks_count": 0,
            "selected_chunks": [],
            "removed_chunks": [],
            "skipped": True,
            "reason": "Input chunks list is empty"
        }
        log_stage(request_id, 6, "Cross Encoder", stage6_data, latency_ms=0.0)
        return []

    config = _get_config()
    model_name = config.get("reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    device = _get_embedding_device(config)
            
    cache_key = f"{model_name}::{device}"
    if cache_key not in _cross_encoder_cache:
        _cross_encoder_cache[cache_key] = _load_cross_encoder(model_name, device=device)
    model = _cross_encoder_cache[cache_key]
    
    # Detect question type for intelligent biasing
    question_analysis = detect_question_type(query)
    question_type = question_analysis["question_type"]
    
    # Form pairs: (query, document_content)
    pairs = [[query, chunk["content"]] for chunk in chunks]
    
    # Predict similarity scores
    scores = model.predict(pairs, show_progress_bar=False)
    
    # Update scores with question-type bias
    for chunk, score in zip(chunks, scores):
        # Get chunk type preference score
        type_score = score_chunk_for_question(chunk, question_type)
        
        # Combine cross-encoder score with type preference
        # Cross-encoder score is typically 0-1, type_score is 0-1
        # Weight: 85% cross-encoder (semantic), 15% type preference (structural)
        combined_score = (score * 0.85) + (type_score * 0.15)
        
        # Preserve raw vector similarity score if available
        if "raw_vector_score" not in chunk:
            chunk["raw_vector_score"] = float(chunk.get("score", 0.0))
            
        chunk["rerank_score"] = float(combined_score)
        # Sigmoid/MinMax Normalization for CrossEncoder logits: 1 / (1 + exp(-x))
        chunk["normalized_score"] = float(1.0 / (1.0 + math.exp(-float(combined_score))))
        chunk["score"] = float(combined_score)
    # ── Configurable thresholding ──────────────────────────
    # Retrieve configurable threshold, default 0.0
    ce_threshold = float(config.get("cross_encoder_threshold", 0.0))
    
    # Filter chunks above threshold
    above_threshold = [c for c in chunks if float(c.get("score", 0.0)) > ce_threshold]
    
    dropped_count = len(chunks) - len(above_threshold)
        
    # Sort descending
    sorted_chunks = sorted(above_threshold, key=lambda x: x["score"], reverse=True)
    
    # Preserve the requested top_k chunks.
    out_chunks = sorted_chunks[:top_k]
    kept_set = set(id(c) for c in out_chunks)

    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000

    evaluated_log = []
    # Note: we iterate over the originally sorted chunks to show dropped chunks in the log too
    all_sorted = sorted(chunks, key=lambda x: x["score"], reverse=True)
    for rank, c in enumerate(all_sorted, 1):
        evaluated_log.append({
            "rank": rank,
            "chunk_id": str(c.get("id") or c.get("metadata", {}).get("hash") or "unknown"),
            "section": c.get("metadata", {}).get("section", "?"),
            "filename": c.get("metadata", {}).get("file", "Unknown"),
            "ce_score": round(float(c.get("rerank_score", 0.0)), 6),
            "combined_score": round(float(c.get("score", 0.0)), 6),
            "status": "KEPT" if id(c) in kept_set else "DROPPED"
        })

    # ── Phase 1: Paper-level retrieval diagnostics ──────────────────────────
    # Compute per-paper chunk counts, scores, and coverage for forensic report.
    paper_diagnostics: dict = {}
    for c in out_chunks:
        paper = (
            c.get("metadata", {}).get("paper_title")
            or c.get("metadata", {}).get("file")
            or "Unknown"
        )
        s = float(c.get("score", 0.0))
        if paper not in paper_diagnostics:
            paper_diagnostics[paper] = {"chunks": 0, "scores": []}
        paper_diagnostics[paper]["chunks"] += 1
        paper_diagnostics[paper]["scores"].append(s)

    paper_summary = []
    for paper, info in sorted(paper_diagnostics.items(), key=lambda x: -x[1]["chunks"]):
        avg_s = sum(info["scores"]) / len(info["scores"]) if info["scores"] else 0.0
        paper_summary.append({
            "paper": paper,
            "chunks": info["chunks"],
            "avg_ce_score": round(avg_s, 4),
            "max_ce_score": round(max(info["scores"]), 4) if info["scores"] else 0.0,
        })

    top_paper = paper_summary[0]["paper"] if paper_summary else "N/A"
    top_paper_chunks = paper_summary[0]["chunks"] if paper_summary else 0
    total_out = len(out_chunks)
    coverage_pct = round(top_paper_chunks / total_out * 100, 1) if total_out else 0.0
    all_ce_scores = [c.get("score", 0.0) for c in out_chunks]
    avg_ce_all = round(sum(all_ce_scores) / len(all_ce_scores), 4) if all_ce_scores else 0.0
    max_ce_all = round(max(all_ce_scores), 4) if all_ce_scores else 0.0

    retrieval_diagnostics = {
        "papers_retrieved": len(paper_diagnostics),
        "top_contributing_paper": top_paper,
        "top_paper_chunk_count": top_paper_chunks,
        "top_paper_coverage_pct": coverage_pct,
        "avg_ce_score_all": avg_ce_all,
        "max_ce_score_all": max_ce_all,
        "paper_breakdown": paper_summary,
    }

    # Push diagnostics into forensic tracer (written to .debug/current_query/)
    try:
        from storage.pipeline_logger import forensic_tracer
        forensic_tracer.retrieval_diagnostics = retrieval_diagnostics
    except Exception:
        pass

    stage6_data = {
        "cross_encoder_enabled": True,
        "reranker_model": model_name,
        "question_type_detected": question_type,
        "input_chunks_count": len(chunks),
        "above_threshold_count": len(above_threshold),
        "threshold_applied": ce_threshold,
        "dropped_by_threshold": dropped_count,
        "output_chunks_count": len(out_chunks),
        "retrieval_diagnostics": retrieval_diagnostics,
        "evaluated_chunks": evaluated_log,
    }
    log_stage(request_id, 6, "Cross Encoder", stage6_data, latency_ms=latency_ms)

    return out_chunks
