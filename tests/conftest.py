"""Isolate tests from user-local Qdrant and registry state."""

import os
import tempfile
from pathlib import Path

_TEST_STATE = Path(tempfile.mkdtemp(prefix="docrag-pytest-"))
os.environ["DOCRAG__QDRANT_PATH"] = str(_TEST_STATE / "qdrant")
os.environ["DOCRAG__REGISTRY_PATH"] = str(_TEST_STATE / "registry.json")

from settings import clear_settings_cache

clear_settings_cache()
