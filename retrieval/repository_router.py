import numpy as np
from typing import List
from storage.vector_store import _get_encoder, _get_config
from storage.registry import RepositoryRegistry, RepoStatus, QUERYABLE_REPO_STATUSES


def rank_repositories(query: str, registry: RepositoryRegistry, top_k: int = 1) -> List[str]:
    """
    Ranks queryable collections based on semantic similarity to the query.
    Returns a list of repo_ids ordered by descending similarity.

    Queryable statuses include READY and partial INDEXING tiers.
    If only one collection exists, returns it without embedding computation.
    """
    repos = registry.list_repositories()
    if not repos:
        return []

    # Filter to queryable collections
    queryable = [r for r in repos if r.status in QUERYABLE_REPO_STATUSES]
    if not queryable:
        return []

    # Single collection — no ranking needed
    if len(queryable) == 1:
        return [queryable[0].repo_id]

    config = _get_config()
    model_name = config.get("embedding_model", "all-MiniLM-L6-v2")
    device = config.get("device", "auto")
    encoder = _get_encoder(model_name, device)

    if "e5" in model_name.lower():
        query_encoded = encoder.encode(f"query: {query}", show_progress_bar=False)
    else:
        query_encoded = encoder.encode(query, show_progress_bar=False)

    repo_descriptions = []
    for r in queryable:
        # Use collection name as primary descriptor — more meaningful for document collections
        # than language/framework (which are always "auto" in DocumentRAG)
        desc = f"Document collection: {r.name}."
        if "e5" in model_name.lower():
            desc = f"passage: {desc}"
        repo_descriptions.append(desc)

    repo_embeddings = encoder.encode(repo_descriptions, show_progress_bar=False)

    # Cosine similarity
    q_norm = query_encoded / (np.linalg.norm(query_encoded) + 1e-9)
    r_norms = repo_embeddings / (np.linalg.norm(repo_embeddings, axis=1, keepdims=True) + 1e-9)
    similarities = np.dot(r_norms, q_norm)

    ranked_indices = np.argsort(similarities)[::-1]

    return [queryable[int(idx)].repo_id for idx in ranked_indices[:top_k]]
