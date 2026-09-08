import json
import os
import threading
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from datetime import datetime

class RepoStatus(str, Enum):
    CREATED = "CREATED"
    READY = "READY"
    INDEXING = "INDEXING"
    INDEXING_TIER0 = "INDEXING_TIER0"
    INDEXING_TIER1 = "INDEXING_TIER1"
    INDEXING_TIER2 = "INDEXING_TIER2"
    FAILED = "FAILED"
    UPDATING = "UPDATING"
    DELETING = "DELETING"
    DELETED = "DELETED"

QUERYABLE_REPO_STATUSES = {
    RepoStatus.READY,
    RepoStatus.INDEXING_TIER0,
    RepoStatus.INDEXING_TIER1,
    RepoStatus.INDEXING_TIER2,
}

class Repository(BaseModel):
    repo_id: str
    name: str
    branch: str = "main"
    description: Optional[str] = None
    commit: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    vector_collection: str
    collection_id: Optional[str] = None
    knowledge_graph: Optional[str] = None
    metadata: Optional[str] = None
    embedding_model: str = "auto"
    source_path: Optional[str] = None
    parser_version: str = "2.0"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    status: RepoStatus = RepoStatus.CREATED
    document_count: int = 0
    chunk_count: int = 0
    tier2_total_chunks: int = 0
    tier2_indexed_chunks: int = 0
    last_error: Optional[str] = None

    def model_post_init(self, __context):
        if not self.collection_id and self.vector_collection:
            self.collection_id = self.vector_collection
        if not self.vector_collection and self.collection_id:
            self.vector_collection = self.collection_id
        if self.chunk_count == 0 and self.tier2_total_chunks > 0:
            self.chunk_count = self.tier2_total_chunks
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc) if 'timezone' in globals() else datetime.utcnow()

class RepositoryRegistry:
    """
    Central authority for multi-tenant repository management.
    """
    def __init__(self, storage_path: str = "./registry.json"):
        self.storage_path = storage_path
        self.repositories: Dict[str, Repository] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for repo_id, repo_data in data.items():
                        self.repositories[repo_id] = Repository(**repo_data)
            except Exception as e:
                print(f"Failed to load registry from {self.storage_path}: {e}")

    def _save(self):
        # NOTE: Caller must hold self._lock
        with open(self.storage_path, "w", encoding="utf-8") as f:
            data = {repo_id: repo.model_dump() for repo_id, repo in self.repositories.items()}
            # Convert datetimes to isoformat for JSON serialization
            json.dump(data, f, indent=4, default=str)

    def register(self, repo: Repository) -> None:
        """Registers a new repository or overwrites an existing one."""
        with self._lock:
            # If attempting to register as READY, verify points count > 0
            if repo.status == RepoStatus.READY and repo.vector_collection:
                try:
                    from storage.vector_store import VectorStoreManager
                    vm = VectorStoreManager(collection_name=repo.vector_collection)
                    if vm.count() == 0:
                        repo.status = RepoStatus.FAILED
                        repo.last_error = "Zero vectors indexed in collection."
                except Exception as e:
                    repo.status = RepoStatus.FAILED
                    repo.last_error = f"Vector count verification failed: {e}"

            self.repositories[repo.repo_id] = repo
            self._save()

        try:
            from retrieval.repository_router import invalidate_router_cache
            invalidate_router_cache(repo.repo_id)
        except Exception:
            pass

    def create_repository(
        self,
        name: str,
        source_path: Optional[str] = None,
        description: Optional[str] = None,
        repo_id: Optional[str] = None,
    ) -> Repository:
        """
        Create and register a new repository with an isolated Qdrant collection.
        """
        import uuid
        rid = repo_id or str(uuid.uuid4())
        coll_name = f"collection_{rid}"
        now = datetime.now(timezone.utc) if 'timezone' in globals() else datetime.utcnow()

        repo = Repository(
            repo_id=rid,
            name=name,
            branch="main",
            description=description,
            vector_collection=coll_name,
            collection_id=coll_name,
            knowledge_graph=f"graph_{rid}",
            metadata=f"metadata_{rid}",
            source_path=source_path,
            parser_version="2.0",
            created_at=now,
            updated_at=now,
            status=RepoStatus.CREATED,
        )
        self.register(repo)
        return repo

    def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Retrieves a repository by its ID, collection ID, or vector collection name."""
        if not repo_id:
            return None
        if repo_id in self.repositories:
            return self.repositories[repo_id]
        for repo in self.repositories.values():
            if repo.vector_collection == repo_id or getattr(repo, "collection_id", None) == repo_id:
                return repo
        if repo_id.startswith("collection_"):
            stripped = repo_id[len("collection_"):]
            if stripped in self.repositories:
                return self.repositories[stripped]
        return None

    def list_repositories(self) -> List[Repository]:
        """Lists all non-deleted repositories."""
        return [
            repo for repo in self.repositories.values()
            if repo.status not in (RepoStatus.DELETED, RepoStatus.DELETING)
        ]

    def update_status(self, repo_id: str, status: RepoStatus) -> None:
        """Updates the status of a repository."""
        with self._lock:
            if repo_id in self.repositories:
                repo = self.repositories[repo_id]
                # If marking as READY, verify count > 0
                if status == RepoStatus.READY and repo.vector_collection:
                    try:
                        from storage.vector_store import VectorStoreManager
                        vm = VectorStoreManager(collection_name=repo.vector_collection)
                        if vm.count() == 0:
                            status = RepoStatus.FAILED
                            repo.last_error = "Zero vectors indexed in collection."
                    except Exception as e:
                        status = RepoStatus.FAILED
                        repo.last_error = f"Vector count verification failed: {e}"

                repo.status = status
                repo.updated_at = datetime.now(timezone.utc) if 'timezone' in globals() else datetime.utcnow()
                self._save()
            else:
                raise ValueError(f"Repository {repo_id} not found in registry.")

        try:
            from retrieval.repository_router import invalidate_router_cache
            invalidate_router_cache(repo_id)
        except Exception:
            pass

    def update_repository(
        self,
        repo_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[RepoStatus] = None,
        source_path: Optional[str] = None,
        document_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
    ) -> Repository:
        """Update metadata fields for a repository."""
        with self._lock:
            if repo_id not in self.repositories:
                raise ValueError(f"Repository {repo_id} not found in registry.")
            repo = self.repositories[repo_id]
            if name is not None:
                repo.name = name
            if description is not None:
                repo.description = description
            if status is not None:
                repo.status = status
            if source_path is not None:
                repo.source_path = source_path
            if document_count is not None:
                repo.document_count = document_count
            if chunk_count is not None:
                repo.chunk_count = chunk_count
                repo.tier2_total_chunks = chunk_count
            repo.updated_at = datetime.now(timezone.utc) if 'timezone' in globals() else datetime.utcnow()
            self._save()

        try:
            from retrieval.repository_router import invalidate_router_cache
            invalidate_router_cache(repo_id)
        except Exception:
            pass
        return repo

    def delete(self, repo_id: str) -> None:
        """Soft-deletes a repository."""
        with self._lock:
            if repo_id in self.repositories:
                self.repositories[repo_id].status = RepoStatus.DELETED
                self.repositories[repo_id].updated_at = datetime.now(timezone.utc) if 'timezone' in globals() else datetime.utcnow()
                self._save()
            else:
                raise ValueError(f"Repository {repo_id} not found in registry.")

        try:
            from retrieval.repository_router import invalidate_router_cache
            invalidate_router_cache(repo_id)
        except Exception:
            pass

    def delete_repository(self, repo_id: str, hard_delete: bool = True) -> Dict[str, Any]:
        """
        Safely deletes a repository, dropping its Qdrant collection,
        invalidating all associated caches, and removing metadata.
        Guarantees other repositories are untouched.
        """
        repo = self.get_repository(repo_id)
        if not repo:
            raise ValueError(f"Repository {repo_id} not found in registry.")

        # 1. Update status to DELETING
        self.update_status(repo_id, RepoStatus.DELETING)

        # 2. Drop Qdrant vector collection
        try:
            from storage.vector_store import VectorStoreManager
            vm = VectorStoreManager(collection_name=repo.vector_collection)
            vm.drop_collection()
        except Exception as e:
            print(f"[Delete] Warning dropping collection {repo.vector_collection}: {e}", flush=True)

        # 3. Invalidate caches for this collection/repository only
        try:
            from retrieval.paper_matcher import invalidate_paper_cache
            invalidate_paper_cache(repo.vector_collection)
        except Exception:
            pass

        try:
            from storage.cache import SemanticCache
            SemanticCache().clear_for_repo(repo_id)
        except Exception:
            pass

        try:
            from retrieval.cross_encoder_rerank import get_ce_score_cache
            get_ce_score_cache().clear_for_collection(repo.vector_collection)
        except Exception:
            pass

        # 4. Remove metadata & snapshot files
        for p in [
            f"metadata_storage/{repo.metadata}.json",
            f"snapshot_storage/{repo_id}.json",
        ]:
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

        # 5. Remove from progress registry
        try:
            from storage.progress import ProgressRegistry
            ProgressRegistry.delete_tracker(repo_id)
        except Exception:
            pass

        # 6. Remove or mark deleted in registry
        with self._lock:
            if hard_delete:
                self.repositories.pop(repo_id, None)
            else:
                repo.status = RepoStatus.DELETED
                repo.updated_at = datetime.now(timezone.utc) if 'timezone' in globals() else datetime.utcnow()
            self._save()

        try:
            from retrieval.repository_router import invalidate_router_cache
            invalidate_router_cache(repo_id)
        except Exception:
            pass

        return {"deleted": True, "repo_id": repo_id, "name": repo.name}

    def reindex_repository(self, repo_id: str, background_tasks=None) -> Dict[str, Any]:
        """
        Reindexes a repository from its source_path.
        Affects only this repository, preserving idempotency.
        """
        repo = self.get_repository(repo_id)
        if not repo:
            raise ValueError(f"Repository {repo_id} not found in registry.")
        if not repo.source_path:
            raise ValueError(f"Repository '{repo.name}' has no source_path to reindex from.")

        # Clear snapshot and caches for this repo only
        try:
            from storage.snapshot import SnapshotManager
            SnapshotManager().delete_snapshot(repo_id)
        except Exception:
            pass

        try:
            from retrieval.paper_matcher import invalidate_paper_cache
            invalidate_paper_cache(repo.vector_collection)
        except Exception:
            pass

        try:
            from storage.cache import SemanticCache
            SemanticCache().clear_for_repo(repo_id)
        except Exception:
            pass

        try:
            from retrieval.cross_encoder_rerank import get_ce_score_cache
            get_ce_score_cache().clear_for_collection(repo.vector_collection)
        except Exception:
            pass

        self.update_status(repo_id, RepoStatus.UPDATING)

        from ingestion.worker import background_ingest_repository
        if background_tasks is not None:
            background_tasks.add_task(
                background_ingest_repository, repo_id, repo.source_path, self
            )
        return {"status": "reindexing_started", "repo_id": repo_id, "name": repo.name}

    def get_repository_status(self, repo_id: str) -> Dict[str, Any]:
        """Return structured status details for a repository."""
        repo = self.get_repository(repo_id)
        if not repo:
            raise ValueError(f"Repository {repo_id} not found in registry.")

        # Real vector count if available
        qdrant_points = 0
        try:
            from storage.vector_store import VectorStoreManager
            vm = VectorStoreManager(collection_name=repo.vector_collection)
            qdrant_points = vm.count()
        except Exception:
            qdrant_points = repo.tier2_indexed_chunks

        return {
            "repo_id": repo.repo_id,
            "name": repo.name,
            "description": repo.description,
            "status": repo.status.value,
            "collection_id": repo.vector_collection,
            "source_path": repo.source_path,
            "document_count": repo.document_count,
            "chunk_count": max(qdrant_points, repo.chunk_count, repo.tier2_indexed_chunks),
            "tier2_indexed_chunks": repo.tier2_indexed_chunks,
            "created_at": repo.created_at,
            "updated_at": repo.updated_at,
            "indexed_at": repo.indexed_at,
            "last_error": repo.last_error,
        }


# ---------------------------------------------------------------------------
# Process-level singleton — eliminates repeated registry.json reads per query.
# Safe for single-process use (standard Uvicorn single-worker deployment).
# ---------------------------------------------------------------------------
_registry_singleton: Optional["RepositoryRegistry"] = None
_registry_singleton_path: Optional[str] = None


def get_registry(storage_path: str = "./registry.json") -> "RepositoryRegistry":
    """
    Return the process-level RepositoryRegistry singleton.
    Loads registry.json exactly once per process (or when storage_path changes).
    All mutations (register, update_status, delete) are reflected immediately
    because they write through to disk AND update self.repositories in-place.
    """
    global _registry_singleton, _registry_singleton_path
    if _registry_singleton is None or _registry_singleton_path != storage_path:
        _registry_singleton = RepositoryRegistry(storage_path=storage_path)
        _registry_singleton_path = storage_path
    return _registry_singleton

