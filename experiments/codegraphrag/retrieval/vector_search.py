from storage.vector_store import VectorStoreManager
from typing import List, Dict, Any

def search_vector(
    query: str,
    top_k: int = 30,
    collection_name: str = "chunks",
    metadata_filters: Dict[str, Any] = None,
    repository_id: str = None,
) -> List[Dict[str, Any]]:
    """
    Search vector database for top_k matching chunks.
    Supports isolated collections, repository verification, and metadata filtering.
    """
    manager = VectorStoreManager(collection_name=collection_name, repository_id=repository_id)
    res = manager.search(
        query,
        top_k=top_k,
        metadata_filters=metadata_filters,
        repository_id=repository_id,
    )
    return res[0] if isinstance(res, tuple) else res
