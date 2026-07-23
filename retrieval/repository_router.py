import numpy as np
from typing import List, Dict, Optional
from storage.vector_store import _get_encoder, _get_config
from storage.registry import RepositoryRegistry, RepoStatus, QUERYABLE_REPO_STATUSES

# Cache: repo_id -> description embedding (numpy array)
_repo_desc_cache: Dict[str, np.ndarray] = {}
_repo_desc_text_cache: Dict[str, str] = {}


def _build_collection_description(repo, model_name: str) -> str:
    """
    Build a rich semantic description of a collection from its actual indexed chunks.
    Uses paper titles, abstract snippets, and section headings from the Qdrant index.
    Falls back to collection name if chunk retrieval fails.
    """
    try:
        from storage.vector_store import VectorStoreManager
        if not repo.vector_collection:
            return f"Document collection: {repo.name}."

        v_manager = VectorStoreManager(collection_name=repo.vector_collection)
        all_chunks = v_manager.get_all_chunks()

        if not all_chunks:
            return f"Document collection: {repo.name}."

        # Collect paper titles
        paper_titles = set()
        abstract_snippets = []
        section_headings = set()

        for chunk in all_chunks:
            meta = chunk.get("metadata", {})
            title = meta.get("paper_title", "")
            if title:
                paper_titles.add(title)
            section = meta.get("section", "")
            if section and len(section) < 80:  # Only clean short headings
                section_headings.add(section)
            # Grab abstract/intro content snippets
            if section and any(kw in section.lower() for kw in ["abstract", "introduction", "summary"]):
                content = chunk.get("content", "")
                if content and len(abstract_snippets) < 3:
                    abstract_snippets.append(content[:300])

        parts = []
        if paper_titles:
            parts.append("Papers: " + "; ".join(sorted(paper_titles)[:5]))
        if abstract_snippets:
            parts.append("Content: " + " | ".join(abstract_snippets))
        if section_headings and not abstract_snippets:
            clean_headings = [h for h in sorted(section_headings) if not h.startswith("[") and not h[0].isdigit() or h[:2].isalpha()]
            parts.append("Sections: " + ", ".join(list(clean_headings)[:10]))

        desc = " ".join(parts) if parts else f"Document collection: {repo.name}."

        if "e5" in model_name.lower():
            desc = f"passage: {desc}"
        return desc

    except Exception:
        return f"Document collection: {repo.name}."


def _get_repo_embedding(repo, encoder, model_name: str) -> Optional[np.ndarray]:
    """Return cached or freshly computed embedding for a repo's description."""
    repo_id = repo.repo_id
    # Invalidate cache if collection was re-indexed (status changed to READY)
    if repo_id not in _repo_desc_cache:
        desc = _build_collection_description(repo, model_name)
        _repo_desc_text_cache[repo_id] = desc
        emb = encoder.encode(desc, show_progress_bar=False)
        _repo_desc_cache[repo_id] = emb
    return _repo_desc_cache[repo_id]


def invalidate_router_cache(repo_id: Optional[str] = None):
    """Call after re-indexing to refresh routing embeddings."""
    if repo_id:
        _repo_desc_cache.pop(repo_id, None)
        _repo_desc_text_cache.pop(repo_id, None)
    else:
        _repo_desc_cache.clear()
        _repo_desc_text_cache.clear()


def rank_repositories(query: str, registry: RepositoryRegistry, top_k: int = 1) -> List[str]:
    """
    Ranks queryable collections based on semantic similarity to the query.
    Uses content-aware descriptions built from actual indexed paper chunks rather
    than just collection names.

    Returns a list of repo_ids ordered by descending similarity.
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

    # Build (or retrieve cached) embeddings for each repo using content-aware descriptions
    repo_embeddings = []
    valid_repos = []
    for r in queryable:
        emb = _get_repo_embedding(r, encoder, model_name)
        if emb is not None:
            repo_embeddings.append(emb)
            valid_repos.append(r)

    if not repo_embeddings:
        return [queryable[0].repo_id]

    repo_embeddings_matrix = np.stack(repo_embeddings)

    # Cosine similarity
    q_norm = query_encoded / (np.linalg.norm(query_encoded) + 1e-9)
    r_norms = repo_embeddings_matrix / (np.linalg.norm(repo_embeddings_matrix, axis=1, keepdims=True) + 1e-9)
    similarities = np.dot(r_norms, q_norm)

    ranked_indices = np.argsort(similarities)[::-1]

    return [valid_repos[int(idx)].repo_id for idx in ranked_indices[:top_k]]
