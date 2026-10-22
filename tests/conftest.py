"""Shared pytest fixtures."""

import os
import tempfile

import pytest

# Set before any module creates the process-wide registry singleton, so test
# runs can never touch the developer's real ./registry.json.
os.environ.setdefault(
    "DOCRAG_REGISTRY_PATH", os.path.join(tempfile.mkdtemp(prefix="docrag_test_"), "registry.json")
)


@pytest.fixture(autouse=True)
def _isolate_registry(tmp_path, monkeypatch):
    """Never let tests read or overwrite the developer's real ./registry.json."""
    import storage.registry as registry_mod
    from api import dependencies

    monkeypatch.setenv("DOCRAG_REGISTRY_PATH", str(tmp_path / "registry.json"))

    reg = dependencies.registry_instance
    saved_path = reg.storage_path
    saved_repos = dict(reg.repositories)
    saved_singleton = registry_mod._registry_singleton
    saved_singleton_path = registry_mod._registry_singleton_path
    reg.storage_path = str(tmp_path / "registry.json")
    registry_mod._registry_singleton = None
    registry_mod._registry_singleton_path = None
    yield
    reg.storage_path = saved_path
    reg.repositories.clear()
    reg.repositories.update(saved_repos)
    registry_mod._registry_singleton = saved_singleton
    registry_mod._registry_singleton_path = saved_singleton_path
