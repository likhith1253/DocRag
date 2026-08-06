from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from retrieval.repository_router import rank_repositories
from storage.registry import RepoStatus


class _FakeRegistry:
    def __init__(self, repos):
        self._repos = repos

    def list_repositories(self):
        return self._repos


class _FakeVectorStoreManager:
    def __init__(self, collection_name="chunks"):
        self.collection_name = collection_name

    def count(self):
        return 1


class _FakeEncoder:
    def encode(self, text, show_progress_bar=False):
        text = text.lower()
        if "flask" in text or "python" in text:
            return np.array([1.0, 0.0], dtype=np.float32)
        if "react" in text or "javascript" in text:
            return np.array([0.0, 1.0], dtype=np.float32)
        return np.array([0.5, 0.5], dtype=np.float32)


def test_rank_repositories_is_deterministic():
    repos = [
        SimpleNamespace(
            repo_id="repo-python",
            status=RepoStatus.READY,
            vector_collection="v1",
            name="flask-backend",
        ),
        SimpleNamespace(
            repo_id="repo-js",
            status=RepoStatus.READY,
            vector_collection="v2",
            name="react-frontend",
        ),
    ]
    registry = _FakeRegistry(repos)

    with patch("storage.vector_store.VectorStoreManager", _FakeVectorStoreManager), \
         patch("retrieval.repository_router._get_encoder", return_value=_FakeEncoder()), \
         patch("retrieval.repository_router._get_repo_embedding", side_effect=lambda repo, encoder, model_name: np.array([1.0, 0.0], dtype=np.float32) if repo.repo_id == "repo-python" else np.array([0.0, 1.0], dtype=np.float32)), \
         patch("retrieval.repository_router._get_config", return_value={"embedding_model": "fake-model", "device": "cpu"}):
        first = rank_repositories("how do I define a flask route in python?", registry, top_k=1)
        second = rank_repositories("where is the react component state updated?", registry, top_k=1)

    assert first == ["repo-python"]
    assert second == ["repo-js"]
