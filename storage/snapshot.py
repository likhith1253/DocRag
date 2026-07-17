import os
import json
import threading
from typing import Dict, List, Optional
from pydantic import BaseModel

class RepositorySnapshot(BaseModel):
    commit: Optional[str] = None
    branch: Optional[str] = None
    head_timestamp: Optional[str] = None
    indexed_commit: Optional[str] = None
    file_hashes: Dict[str, str] = {}
    chunk_hashes: Dict[str, List[str]] = {}
    embedded_chunk_hashes: Dict[str, List[str]] = {}
    graph_version: str = "1.0"
    embedding_version: str = "1.0"
    parser_version: str = "1.0"


class SnapshotManager:
    """
    Manages incremental indexing snapshots for repositories.
    """
    _snapshots: Dict[str, RepositorySnapshot] = {}
    _lock = threading.Lock()
    
    def __init__(self, storage_dir: str = "./snapshot_storage"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        
    def _get_path(self, repo_id: str) -> str:
        return os.path.join(self.storage_dir, f"{repo_id}.json")
        
    def get_snapshot(self, repo_id: str) -> RepositorySnapshot:
        with self._lock:
            if repo_id in self._snapshots:
                return self._snapshots[repo_id]
                
            path = self._get_path(repo_id)
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    snapshot = RepositorySnapshot(**data)
                    self._snapshots[repo_id] = snapshot
                    return snapshot
                except Exception as e:
                    print(f"Error loading snapshot for {repo_id}: {e}")
                    
            snapshot = RepositorySnapshot()
            self._snapshots[repo_id] = snapshot
            return snapshot
            
    def save_snapshot(self, repo_id: str, snapshot: RepositorySnapshot):
        with self._lock:
            self._snapshots[repo_id] = snapshot
            path = self._get_path(repo_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot.model_dump(), f, indent=2, default=str)
                
    def delete_snapshot(self, repo_id: str):
        with self._lock:
            if repo_id in self._snapshots:
                del self._snapshots[repo_id]
            path = self._get_path(repo_id)
            if os.path.exists(path):
                os.remove(path)
