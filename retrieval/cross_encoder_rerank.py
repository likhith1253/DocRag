import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any
from storage.vector_store import _get_config
from retrieval.query_analyzer import detect_question_type, score_chunk_for_question

_cross_encoder_cache: Dict[str, CrossEncoder] = {}

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
    device = config.get("device", "cpu")
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
            
    cache_key = f"{model_name}::{device}"
    if cache_key not in _cross_encoder_cache:
        _cross_encoder_cache[cache_key] = CrossEncoder(model_name, device=device)
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
        import math
        chunk["normalized_score"] = float(1.0 / (1.0 + math.exp(-float(combined_score))))
        chunk["score"] = float(combined_score)
        
    # Sort descending
    sorted_chunks = sorted(chunks, key=lambda x: x["score"], reverse=True)
    out_chunks = sorted_chunks[:top_k]
    removed_chunks_list = sorted_chunks[top_k:]

    t_end = time.perf_counter()
    latency_ms = (t_end - t_start) * 1000

    evaluated_log = []
    for rank, c in enumerate(sorted_chunks, 1):
        evaluated_log.append({
            "rank": rank,
            "chunk_id": str(c.get("id") or c.get("metadata", {}).get("hash") or "unknown"),
            "section": c.get("metadata", {}).get("section", "?"),
            "filename": c.get("metadata", {}).get("file", "Unknown"),
            "ce_score": round(float(c.get("rerank_score", 0.0)), 6),
            "combined_score": round(float(c.get("score", 0.0)), 6),
            "status": "KEPT" if rank <= top_k else "DROPPED"
        })

    stage6_data = {
        "cross_encoder_enabled": True,
        "reranker_model": model_name,
        "question_type_detected": question_type,
        "input_chunks_count": len(chunks),
        "output_chunks_count": len(out_chunks),
        "evaluated_chunks": evaluated_log
    }
    log_stage(request_id, 6, "Cross Encoder", stage6_data, latency_ms=latency_ms)

    return out_chunks
