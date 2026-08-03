import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
import numpy as np
from typing import List, Dict, Any, Optional

def mmr_rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 5,
    lambda_param: float = None,   # None = read from config (default 0.7)
    query_vector: Optional[np.ndarray] = None,
) -> List[Dict[str, Any]]:
    """
    Rerank chunks using Maximal Marginal Relevance (MMR).

    query: The user query string.
    chunks: Retrieved chunk dicts (each having "content", "score", optional "vector").
    top_k: Number of final chunks to return.
    lambda_param: Balance between relevance (1.0) and diversity (0.0).
    query_vector: Optional pre-computed query embedding (numpy array).
                  When provided, the query is NOT re-encoded, saving ~150ms on CPU.
    """
    if not chunks:
        print("=" * 60, flush=True)
        print("STAGE 5: MMR", flush=True)
        print("=" * 60, flush=True)
        print("MMR enabled?: YES", flush=True)
        print("MMR SKIPPED: Input chunks list is empty (0 chunks)", flush=True)
        return []
    if len(chunks) <= 1:
        print("=" * 60, flush=True)
        print("STAGE 5: MMR", flush=True)
        print("=" * 60, flush=True)
        print("MMR enabled?: YES", flush=True)
        print(f"MMR SKIPPED: Input chunks count is {len(chunks)} (<= 1)", flush=True)
        return chunks

    from storage.vector_store import _get_encoder, _get_config
    config = _get_config()
    embedding_model_name = config.get("embedding_model", "all-MiniLM-L6-v2")
    device = config.get("device", "auto")

    # Read lambda from config if caller did not override (BUG-6 fix)
    if lambda_param is None:
        lambda_param = float(
            config.get("retrieval", {}).get("mmr_lambda", 0.7)
        )

    # ------------------------------------------------------------------
    # Determine which chunks already have stored vectors and which need
    # encoding.  Chunks returned by VectorStoreManager.search() carry a
    # "vector" key (stored Qdrant embedding).  KG-expanded chunks do not.
    # We only run the encoder for the subset that lacks pre-computed vectors.
    # ------------------------------------------------------------------
    needs_encode_idx = [i for i, c in enumerate(chunks) if "vector" not in c]
    has_vector_idx   = [i for i, c in enumerate(chunks) if "vector" in c]

    encoder_needed = (query_vector is None) or bool(needs_encode_idx)
    encoder = _get_encoder(embedding_model_name, device=device) if encoder_needed else None

    # ---- Query vector ----
    if query_vector is None:
        query_emb = encoder.encode(query, show_progress_bar=False)
    else:
        query_emb = query_vector

    # ---- Chunk vectors ----
    # Start with a zero matrix; fill pre-computed and freshly encoded slots.
    if has_vector_idx:
        # Infer dimensionality from the first stored vector
        dim = len(chunks[has_vector_idx[0]]["vector"])
    elif encoder is not None:
        # get_embedding_dimension() is the current API;
        # fall back to the deprecated name for older sentence-transformers versions.
        dim_fn = getattr(encoder, "get_embedding_dimension", None) or encoder.get_sentence_embedding_dimension
        dim = dim_fn()
    else:
        dim = len(query_emb)

    chunk_embs = np.zeros((len(chunks), dim), dtype=np.float32)

    # Fill pre-computed vectors (no encoder call)
    for i in has_vector_idx:
        chunk_embs[i] = np.asarray(chunks[i]["vector"], dtype=np.float32)

    # Batch-encode only the chunks that don't have stored vectors
    if needs_encode_idx and encoder is not None:
        texts = [chunks[i]["content"] for i in needs_encode_idx]
        encoded = encoder.encode(texts, show_progress_bar=False)
        for slot, i in enumerate(needs_encode_idx):
            chunk_embs[i] = encoded[slot]

    # ---- Normalize for cosine similarity ----
    query_norm = np.linalg.norm(query_emb)
    if query_norm > 0:
        query_emb = query_emb / query_norm

    chunk_norms = np.linalg.norm(chunk_embs, axis=1, keepdims=True)
    chunk_norms[chunk_norms == 0] = 1.0
    chunk_embs = chunk_embs / chunk_norms

    # ---- MMR selection ----
    sim_to_query = np.dot(chunk_embs, query_emb)
    sim_between_chunks = np.dot(chunk_embs, chunk_embs.T)

    selected_indices = []
    unselected_indices = list(range(len(chunks)))

    first_idx = int(np.argmax(sim_to_query))
    selected_indices.append(first_idx)
    unselected_indices.remove(first_idx)

    while len(selected_indices) < top_k and unselected_indices:
        mmr_scores = []
        for idx in unselected_indices:
            relevance = sim_to_query[idx]
            max_sim_to_selected = max(sim_between_chunks[idx, s_idx] for s_idx in selected_indices)
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
            mmr_scores.append((mmr_score, idx))

        best_score, best_idx = max(mmr_scores, key=lambda x: x[0])
        selected_indices.append(best_idx)
        unselected_indices.remove(best_idx)

    res = [chunks[idx] for idx in selected_indices]
    selected_ids = [
        chunks[idx].get("id") or chunks[idx].get("metadata", {}).get("hash") or f"idx_{idx}"
        for idx in selected_indices
    ]

    print("=" * 60, flush=True)
    print("STAGE 5: MMR", flush=True)
    print("=" * 60, flush=True)
    print("MMR enabled?: YES", flush=True)
    print(f"lambda_param: {lambda_param}", flush=True)
    print(f"Input chunks: {len(chunks)}", flush=True)
    print(f"Output chunks: {len(res)}", flush=True)
    print(f"Selected chunk IDs: {selected_ids}", flush=True)

    # Log dropped chunks so we can diagnose if the target chunk was evicted here
    if unselected_indices:
        print(f"Dropped chunks ({len(unselected_indices)} total):", flush=True)
        for idx in unselected_indices:
            c = chunks[idx]
            dropped_id = c.get("id") or c.get("metadata", {}).get("hash", f"idx_{idx}")
            q_sim = float(sim_to_query[idx])
            sec = c.get("metadata", {}).get("section", "?")
            print(
                f"  DROPPED idx={idx} query_sim={q_sim:.4f} "
                f"section='{sec}' id={str(dropped_id)[:12]}",
                flush=True,
            )

    return res
