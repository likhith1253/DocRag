"""
DocumentRAG Repository & Collection Management API.
Handles CRUD and indexing for multi-repository document collections.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid
import os

from storage.registry import RepositoryRegistry, Repository, RepoStatus
from api.dependencies import get_registry
from ingestion.worker import background_ingest_repository

router = APIRouter(tags=["repository"])


class CreateRepositoryRequest(BaseModel):
    name: str
    branch: str = "main"
    description: Optional[str] = ""
    source_path: Optional[str] = None


class UpdateRepositoryRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[RepoStatus] = None
    source_path: Optional[str] = None


@router.post("/", response_model=Repository)
@router.post("", response_model=Repository)
def create_repository(
    req: CreateRepositoryRequest,
    background_tasks: BackgroundTasks,
    registry: RepositoryRegistry = Depends(get_registry),
):
    repo = registry.create_repository(
        name=req.name,
        description=req.description or "",
        source_path=req.source_path,
    )
    if req.source_path:
        registry.update_status(repo.repo_id, RepoStatus.INDEXING)
        background_tasks.add_task(
            background_ingest_repository, repo.repo_id, req.source_path, registry
        )
    return repo


@router.get("/", response_model=List[Repository])
@router.get("", response_model=List[Repository])
def list_repositories(registry: RepositoryRegistry = Depends(get_registry)):
    return registry.list_repositories()


@router.get("/{repo_id}", response_model=Repository)
def get_repository(
    repo_id: str, registry: RepositoryRegistry = Depends(get_registry)
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


@router.get("/{repo_id}/status")
def get_repository_status(
    repo_id: str, registry: RepositoryRegistry = Depends(get_registry)
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return registry.get_repository_status(repo_id)


@router.put("/{repo_id}", response_model=Repository)
def update_repository(
    repo_id: str,
    req: UpdateRepositoryRequest,
    registry: RepositoryRegistry = Depends(get_registry),
):
    try:
        return registry.update_repository(
            repo_id=repo_id,
            name=req.name,
            description=req.description,
            status=req.status,
            source_path=req.source_path,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{repo_id}/index")
@router.post("/{repo_id}/reindex")
def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    registry: RepositoryRegistry = Depends(get_registry),
):
    repo = registry.get_repository(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    if not repo.source_path:
        raise HTTPException(
            status_code=400,
            detail=f"Repository '{repo.name}' has no source_path to reindex from",
        )

    # Prevent concurrent duplicate indexing tasks
    status_val = repo.status.value if hasattr(repo.status, "value") else str(repo.status)
    if status_val in ["INDEXING", "UPDATING"]:
        return {"message": "Repository is already indexing", "repo_id": repo_id}

    try:
        return registry.reindex_repository(repo_id, background_tasks=background_tasks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindexing failed: {e}")


@router.delete("/{repo_id}")
def delete_repository(
    repo_id: str, registry: RepositoryRegistry = Depends(get_registry)
):
    try:
        return registry.delete_repository(repo_id, hard_delete=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
