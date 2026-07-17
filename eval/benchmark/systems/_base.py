"""
eval.benchmark.systems._base
==============================
Shared base class for all system adapters.

Provides:
  - Config loading with override support (Amendment 6)
  - Memory measurement (cross-platform)
  - Chunk normalization (file_path extraction from various metadata formats)

All concrete systems inherit from BaseSystem, not directly from RetrievalSystem.
"""

from __future__ import annotations

import ctypes
import os
import platform
import time
import yaml
from typing import Dict, Any, List, Optional

from eval.benchmark.interface import RetrievalSystem, RetrievedChunk, SystemResponse

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.yaml"))


def _load_config(overrides: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Load config.yaml and apply any overrides.

    Supports dotted key paths for nested overrides:
      {"retrieval.use_graph": False} sets config["retrieval"]["use_graph"] = False.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if overrides:
        for key_path, value in overrides.items():
            keys = key_path.split(".")
            d = config
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value
    return config


def _normalize_chunk(raw_chunk: Dict[str, Any]) -> RetrievedChunk:
    """
    Convert an internal chunk dict (from storage layer) to a RetrievedChunk.

    Handles the common metadata format used by VectorStoreManager.search():
      {
        "content": str,
        "score": float,
        "metadata": {
          "file": str,   ← relative path
          "hash": str,
          "language": str,
          ...
        }
      }
    """
    metadata = raw_chunk.get("metadata", {})
    file_path = (
        metadata.get("file")
        or metadata.get("file_path")
        or raw_chunk.get("file_path")
        or ""
    )
    return RetrievedChunk(
        content=raw_chunk.get("content", ""),
        file_path=str(file_path),
        score=float(raw_chunk.get("score", 0.0)),
        metadata=metadata,
    )


class BaseSystem(RetrievalSystem):
    """
    Base class for all evaluated systems.

    Provides config loading, memory measurement stubs, and chunk normalization.
    Concrete systems override `retrieve()` and `answer()`.
    """

    def __init__(self, config_overrides: Dict[str, Any] = None):
        self.config_overrides = config_overrides or {}
        self.config = _load_config(self.config_overrides)

    def configuration(self) -> Dict[str, Any]:
        """Return the effective configuration (base config + overrides)."""
        return {
            "config_overrides": self.config_overrides,
            "embedding_model": self.config.get("embedding_model"),
            "reranker_model": self.config.get("reranker_model"),
            "retrieval": self.config.get("retrieval", {}),
            "chunking": self.config.get("chunking", {}),
        }

    def _normalize_chunks(self, raw_chunks: List[Dict[str, Any]]) -> List[RetrievedChunk]:
        """Normalize a list of raw chunk dicts to RetrievedChunk objects."""
        chunks = []
        for i, raw in enumerate(raw_chunks):
            chunk = _normalize_chunk(raw)
            chunk.rank = i + 1
            chunks.append(chunk)
        return chunks
