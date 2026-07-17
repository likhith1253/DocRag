import time
import threading
from typing import Dict, Any, Optional

class IndexingProgressTracker:
    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self.stage = "queued"
        self.percentage = 0.0
        self.files_processed = 0
        self.files_total = 0
        self.chunks_processed = 0
        self.chunks_total = 0
        self.embeddings_completed = 0
        self.embedding_rate = 0.0
        self.eta_seconds = -1.0
        self.status = "INDEXING"
        self.heartbeat = time.time()
        self.start_time = time.time()
        self.embedding_start_time = None
        self.lock = threading.Lock()

    def update(self, **kwargs):
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            self.heartbeat = time.time()
            self._recalculate_percentage_and_eta()

    def update_heartbeat(self):
        with self.lock:
            self.heartbeat = time.time()

    def _recalculate_percentage_and_eta(self):
        if self.stage == "completed":
            self.percentage = 100.0
            self.eta_seconds = 0.0
            return
        elif self.stage == "failed":
            self.eta_seconds = -1.0
            return

        now = time.time()
        
        # Calculate rate if embedding started
        if self.embedding_start_time and self.embeddings_completed > 0:
            elapsed = now - self.embedding_start_time
            if elapsed > 0.1:
                self.embedding_rate = self.embeddings_completed / elapsed
                # Estimate ETA
                remaining = self.chunks_total - self.embeddings_completed
                if self.embedding_rate > 0:
                    self.eta_seconds = remaining / self.embedding_rate
                else:
                    self.eta_seconds = -1.0
            else:
                self.embedding_rate = 0.0
                self.eta_seconds = -1.0
        else:
            self.embedding_rate = 0.0
            self.eta_seconds = -1.0

        if self.stage == "discovering":
            self.percentage = 5.0
        elif self.stage == "parsing":
            ratio = (self.files_processed / max(1, self.files_total))
            self.percentage = 10.0 + ratio * 35.0
        elif self.stage == "kg_construction":
            self.percentage = 45.0
        elif self.stage == "metadata_generation":
            self.percentage = 50.0
        elif self.stage == "indexing_tier1":
            ratio = (self.embeddings_completed / max(1, self.chunks_total))
            self.percentage = 55.0 + ratio * 20.0
        elif self.stage == "indexing_tier2":
            ratio = (self.embeddings_completed / max(1, self.chunks_total))
            self.percentage = 75.0 + ratio * 24.0
        elif self.stage == "completed":
            self.percentage = 100.0
        else:
            self.percentage = 0.0

        self.percentage = min(99.0, max(0.0, self.percentage))

    def to_dict(self) -> dict:
        with self.lock:
            return {
                "stage": self.stage,
                "percentage": round(self.percentage, 2),
                "files_processed": self.files_processed,
                "files_total": self.files_total,
                "chunks_processed": self.chunks_processed,
                "chunks_total": self.chunks_total,
                "embeddings_completed": self.embeddings_completed,
                "embedding_rate": round(self.embedding_rate, 2),
                "eta_seconds": round(self.eta_seconds, 2) if self.eta_seconds >= 0 else -1.0,
                "status": self.status
            }

class ProgressRegistry:
    _progress: Dict[str, IndexingProgressTracker] = {}
    _lock = threading.Lock()

    @classmethod
    def get_tracker(cls, repo_id: str) -> IndexingProgressTracker:
        with cls._lock:
            if repo_id not in cls._progress:
                cls._progress[repo_id] = IndexingProgressTracker(repo_id)
            return cls._progress[repo_id]

    @classmethod
    def delete_tracker(cls, repo_id: str):
        with cls._lock:
            cls._progress.pop(repo_id, None)

    @classmethod
    def check_heartbeats(cls, registry):
        with cls._lock:
            now = time.time()
            for repo_id, tracker in list(cls._progress.items()):
                with tracker.lock:
                    if tracker.status in ["INDEXING", "UPDATING", "INDEXING_TIER0", "INDEXING_TIER1", "INDEXING_TIER2"]:
                        # 300-second timeout for heartbeat inactivity under heavy CPU load
                        if now - tracker.heartbeat > 300.0:
                            tracker.status = "FAILED"
                            tracker.stage = "failed"
                            tracker.eta_seconds = -1.0
                            print(f"[Heartbeat] Timeout detected for {repo_id}. Marking as FAILED.")
                            try:
                                registry.update_status(repo_id, "FAILED")
                            except Exception as e:
                                print(f"[Heartbeat] Error updating registry: {e}")
