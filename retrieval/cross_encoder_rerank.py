import os
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any
from storage.vector_store import _get_config

_cross_encoder_cache: Dict[str, CrossEncoder] = {}

def rerank_cross_encoder(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Rerank chunks using a Cross-Encoder model.
    """
    if not chunks:
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
    
    # Form pairs: (query, document_content)
    pairs = [[query, chunk["content"]] for chunk in chunks]
    
    # Predict similarity scores
    scores = model.predict(pairs, show_progress_bar=False)
    
    # Update scores
    for chunk, score in zip(chunks, scores):
        # Store score as float
        chunk["score"] = float(score)
        
    # Sort descending
    sorted_chunks = sorted(chunks, key=lambda x: x["score"], reverse=True)
    return sorted_chunks[:top_k]
