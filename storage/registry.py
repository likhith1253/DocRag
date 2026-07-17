import json
import os
import threading
from enum import Enum
from typing import Optional, Dict, List
from pydantic import BaseModel
from datetime import datetime

class RepoStatus(str, Enum):
    READY = "READY"
    INDEXING = "INDEXING"
    INDEXING_TIER0 = "INDEXING_TIER0"
    INDEXING_TIER1 = "INDEXING_TIER1"
    INDEXING_TIER2 = "INDEXING_TIER2"
    FAILED = "FAILED"
    UPDATING = "UPDATING"
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
    branch: str
    commit: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    vector_collection: str
    knowledge_graph: str
    metadata: str
    embedding_model: str
    source_path: Optional[str] = None
    parser_version: str
    indexed_at: Optional[datetime] = None
    status: RepoStatus
    tier2_total_chunks: int = 0
    tier2_indexed_chunks: int = 0
    last_error: Optional[str] = None

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
            self.repositories[repo.repo_id] = repo
            self._save()

    def get_repository(self, repo_id: str) -> Optional[Repository]:
        """Retrieves a repository by its ID."""
        return self.repositories.get(repo_id)

    def list_repositories(self) -> List[Repository]:
        """Lists all non-deleted repositories."""
        return [repo for repo in self.repositories.values() if repo.status != RepoStatus.DELETED]

    def update_status(self, repo_id: str, status: RepoStatus) -> None:
        """Updates the status of a repository."""
        with self._lock:
            if repo_id in self.repositories:
                self.repositories[repo_id].status = status
                self._save()
            else:
                raise ValueError(f"Repository {repo_id} not found in registry.")

    def delete(self, repo_id: str) -> None:
        """Soft-deletes a repository."""
        with self._lock:
            if repo_id in self.repositories:
                self.repositories[repo_id].status = RepoStatus.DELETED
                self._save()
            else:
                raise ValueError(f"Repository {repo_id} not found in registry.")


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

