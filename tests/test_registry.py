import os
import pytest
from datetime import datetime, timezone
from storage.registry import RepositoryRegistry, Repository, RepoStatus

@pytest.fixture
def registry():
    # Use a temporary file for tests
    test_path = "./test_registry.json"
    if os.path.exists(test_path):
        os.remove(test_path)
    reg = RepositoryRegistry(storage_path=test_path)
    yield reg
    if os.path.exists(test_path):
        os.remove(test_path)

def test_register_and_get(registry):
    repo = Repository(
        repo_id="repo1",
        name="test_repo",
        branch="main",
        vector_collection="coll_repo1",
        knowledge_graph="kg_repo1",
        metadata="meta_repo1",
        embedding_model="test-model",
        parser_version="1.0",
        status=RepoStatus.READY,
        indexed_at=datetime.now(timezone.utc)
    )
    registry.register(repo)
    
    fetched = registry.get_repository("repo1")
    assert fetched is not None
    assert fetched.name == "test_repo"
    assert fetched.status == RepoStatus.READY

def test_update_status(registry):
    repo = Repository(
        repo_id="repo2",
        name="test_repo2",
        branch="main",
        vector_collection="coll_repo2",
        knowledge_graph="kg_repo2",
        metadata="meta_repo2",
        embedding_model="test-model",
        parser_version="1.0",
        status=RepoStatus.INDEXING
    )
    registry.register(repo)
    registry.update_status("repo2", RepoStatus.READY)
    
    fetched = registry.get_repository("repo2")
    assert fetched.status == RepoStatus.READY

def test_delete_and_list(registry):
    repo3 = Repository(
        repo_id="repo3",
        name="test_repo3",
        branch="main",
        vector_collection="coll_repo3",
        knowledge_graph="kg_repo3",
        metadata="meta_repo3",
        embedding_model="test-model",
        parser_version="1.0",
        status=RepoStatus.READY
    )
    registry.register(repo3)
    assert len(registry.list_repositories()) == 1
    
    registry.delete("repo3")
    assert len(registry.list_repositories()) == 0
    fetched = registry.get_repository("repo3")
    assert fetched.status == RepoStatus.DELETED
