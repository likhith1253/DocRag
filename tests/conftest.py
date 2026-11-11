"""Isolate tests from user-local Qdrant, registry and cache state."""

import os
import tempfile
from pathlib import Path

_TEST_STATE = Path(tempfile.mkdtemp(prefix="docrag-pytest-"))
os.environ["DOCRAG__QDRANT_PATH"] = str(_TEST_STATE / "qdrant")
os.environ["DOCRAG__REGISTRY_PATH"] = str(_TEST_STATE / "registry.json")
os.environ["DOCRAG__CACHE_DIR"] = str(_TEST_STATE / "cache")
os.environ["DOCRAG__SEMANTIC_CACHE_PATH"] = str(_TEST_STATE / "semantic_cache.db")
os.environ["DOCRAG__EMBEDDING_CACHE_PATH"] = str(_TEST_STATE / "embedding_cache.db")

from settings import clear_settings_cache  # noqa: E402

clear_settings_cache()
