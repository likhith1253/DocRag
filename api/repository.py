"""
DocumentRAG Collection Management API.
Handles CRUD for document collections (formerly called repositories).
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import os

from storage.registry import RepositoryRegistry, Repository, RepoStatus
from api.dependencies import get_registry
from ingestion.worker import background_ingest_repository

router = APIRouter(prefix="/repository", tags=["repository"])


class CreateRepositoryRequest(BaseModel):
    name: str
    branch: str = "main"
    source_path: str = None


class UpdateRepositoryRequest(BaseModel):
    name: str = None
    status: RepoStatus = None


@router.post("/", response_model=Repository)
def create_repository(
    req: CreateRepositoryRequest,
    background_tasks: BackgroundTasks,
    registry: RepositoryRegistry = Depends(get_registry),
):
    repo_id = str(uuid.uuid4())
    repo = Repository(
        repo_id=repo_id,
        name=req.name,
        branch=req.branch,
        language="auto",
        framework="auto",
        vector_collection=f"collection_{repo_id}",
        knowledge_graph=f"graph_{repo_id}",
        metadata=f"metadata_{repo_id}",
        embedding_model="auto",
        source_path=req.source_path,
        parser_version="2.0",
        status=RepoStatus.INDEXING,
        indexed_at=datetime.now(timezone.utc),
    )
    registry.register(repo)

    if req.source_path:
        background_tasks.add_task(
            background_ingest_repository, repo_id, req.source_path, registry
        )
    return repo


@router.get("/", response_model=List[Repository])
def list_repositories(registry: RepositoryRegistry = Depends(get_registry)):
    return registry.list_repositories()


@router.get("/{repo_id}/status")
def get_repository_status(
    repo_id: str, registry: RepositoryRegistry = Depends(get_registry)
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"repo_id": repo.repo_id, "status": repo.status}


@router.put("/{repo_id}", response_model=Repository)
def update_repository(
    repo_id: str,
    req: UpdateRepositoryRequest,
    registry: RepositoryRegistry = Depends(get_registry),
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Collection not found")

    if req.name is not None:
        repo.name = req.name
    if req.status is not None:
        repo.status = req.status

    registry.register(repo)
    return repo


@router.post("/{repo_id}/reindex")
def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    registry: RepositoryRegistry = Depends(get_registry),
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not repo.source_path:
        raise HTTPException(
            status_code=400,
            detail="Collection has no source_path to reindex from",
        )

    # Prevent concurrent duplicate indexing tasks
    if repo.status in [
        RepoStatus.INDEXING,
        RepoStatus.INDEXING_TIER0,
        RepoStatus.INDEXING_TIER1,
        RepoStatus.INDEXING_TIER2,
        RepoStatus.UPDATING,
    ]:
        return {"message": "Collection is already indexing", "repo_id": repo_id}

    registry.update_status(repo_id, RepoStatus.UPDATING)
    background_tasks.add_task(
        background_ingest_repository, repo_id, repo.source_path, registry
    )
    return {"message": "Reindexing started", "repo_id": repo_id}


@router.delete("/{repo_id}")
def delete_repository(
    repo_id: str, registry: RepositoryRegistry = Depends(get_registry)
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Collection not found")

    # 1. Delete Qdrant vector collection
    try:
        from storage.vector_store import VectorStoreManager
        v_manager = VectorStoreManager(collection_name=repo.vector_collection)
        v_manager.client.delete_collection(collection_name=repo.vector_collection)
    except Exception as e:
        print(f"[Delete] Error deleting vector collection: {e}")

    # 2. Remove persisted storage files
    def _try_remove(path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[Delete] Could not remove {path}: {e}")

    _try_remove(f"metadata_storage/{repo.metadata}.json")
    _try_remove(f"kg_storage/{repo.knowledge_graph}.json")   # may not exist in DocumentRAG
    _try_remove(f"snapshot_storage/{repo_id}.json")

    # 3. Remove from in-memory progress registry
    try:
        from storage.progress import ProgressRegistry
        ProgressRegistry.delete_tracker(repo_id)
    except Exception:
        pass

    # 4. Soft-delete in registry
    registry.delete(repo_id)
    return {"message": "Collection deleted", "repo_id": repo_id}
