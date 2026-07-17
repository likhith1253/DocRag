import os
import pytest
from datetime import datetime, timezone
from storage.registry import RepositoryRegistry, Repository, RepoStatus
from retrieval.repository_router import rank_repositories

@pytest.fixture
def registry():
    test_path = "./test_registry_router.json"
    if os.path.exists(test_path):
        os.remove(test_path)
    reg = RepositoryRegistry(storage_path=test_path)
    
    # Add some repositories
    reg.register(Repository(
        repo_id="repo-python",
        name="flask-backend",
        branch="main",
        language="python",
        framework="flask",
        vector_collection="v1",
        knowledge_graph="kg1",
        metadata="m1",
        embedding_model="auto",
        parser_version="1.0",
        status=RepoStatus.READY,
        indexed_at=datetime.now(timezone.utc)
    ))
    
    reg.register(Repository(
        repo_id="repo-js",
        name="react-frontend",
        branch="main",
        language="javascript",
        framework="react",
        vector_collection="v2",
        knowledge_graph="kg2",
        metadata="m2",
        embedding_model="auto",
        parser_version="1.0",
        status=RepoStatus.READY,
        indexed_at=datetime.now(timezone.utc)
    ))
    
    yield reg
    if os.path.exists(test_path):
        os.remove(test_path)

def test_rank_repositories(registry):
    # Query related to python/flask
    top_repos = rank_repositories("how do I define a flask route in python?", registry, top_k=1)
    assert len(top_repos) == 1
    assert top_repos[0] == "repo-python"
    
    # Query related to react/javascript
    top_repos2 = rank_repositories("where is the react component state updated?", registry, top_k=1)
    assert len(top_repos2) == 1
    assert top_repos2[0] == "repo-js"
