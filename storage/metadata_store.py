import os
import json
from typing import Dict, Any, List

class MetadataStoreManager:
    def __init__(self, storage_path: str = "./metadata_store.json"):
        self.storage_path = storage_path
        self.store = {}
        self.load()

    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.store = json.load(f)
            except Exception:
                self.store = {}

    def save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.store, f, indent=2)

    def add_metadata(self, chunk_hash: str, metadata: Dict[str, Any]):
        """
        Store per-chunk metadata keying by the chunk's content hash.
        NOTE: Calls save() after every insert. Use add_metadata_batch() when
        inserting many chunks to avoid O(N) disk writes.
        """
        self.store[chunk_hash] = metadata
        self.save()

    def add_metadata_batch(self, items: Dict[str, Dict[str, Any]]):
        """
        Bulk-insert metadata for many chunks with a single save() call.
        items: {chunk_hash: metadata_dict, ...}
        Reduces disk writes from O(N) to O(1) during ingestion.
        """
        self.store.update(items)
        self.save()
        
    def remove_metadata(self, chunk_hashes: List[str]):
        """
        Remove metadata for deleted chunks.
        """
        for chash in chunk_hashes:
            self.store.pop(chash, None)
        self.save()

    def get_metadata(self, chunk_hash: str) -> Dict[str, Any]:
        """
        Get metadata by chunk hash.
        """
        return self.store.get(chunk_hash)
