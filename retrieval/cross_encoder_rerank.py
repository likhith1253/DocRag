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
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Rerank chunks using a Cross-Encoder model with question-type-aware biasing.
    """
    if not chunks:
        print("=" * 60, flush=True)
        print("STAGE 6: CROSS ENCODER", flush=True)
        print("=" * 60, flush=True)
        print("Cross Encoder enabled?: YES", flush=True)
        print("Cross Encoder SKIPPED: Input chunks list is empty (0 chunks)", flush=True)
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

    sorted_order = [c.get("id") or c.get("metadata", {}).get("hash") or "unknown" for c in out_chunks]
    score_list = [c.get("score") for c in out_chunks]

    print("=" * 60, flush=True)
    print("STAGE 6: CROSS ENCODER", flush=True)
    print("=" * 60, flush=True)
    print("Cross Encoder enabled?: YES", flush=True)
    print(f"Input chunks: {len(chunks)}", flush=True)
    print(f"Output chunks (top_k={top_k}): {len(out_chunks)}", flush=True)
    # Log ALL ranked chunks so ranks beyond top_k are visible for debugging
    for rank, c in enumerate(sorted_chunks, 1):
        cid = str(c.get("id") or c.get("metadata", {}).get("hash") or "unknown")[:12]
        sec = c.get("metadata", {}).get("section", "?")
        ce_s = c.get("rerank_score", 0.0)
        kept = "✓ KEPT" if rank <= top_k else "✗ DROPPED"
        print(
            f"  Rank #{rank:2d} [{kept}] ce_score={ce_s:.4f} "
            f"section='{sec}' id={cid}",
            flush=True,
        )

    return out_chunks
