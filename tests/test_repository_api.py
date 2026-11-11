"""Repository CRUD endpoints (model-free: background ingestion is stubbed)."""

import pytest
from fastapi.testclient import TestClient

import api.repository as repo_mod
from api.dependencies import get_registry
from api.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _stub_ingestion(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "papers").mkdir(parents=True)
    monkeypatch.setenv("DOCRAG_DATA_ROOTS", str(root))
    monkeypatch.setattr(repo_mod, "background_ingest_repository", lambda *a, **k: None)
    # Registry.reindex_repository imports the worker lazily; stub that too.
    import ingestion.worker as worker

    monkeypatch.setattr(worker, "background_ingest_repository", lambda *a, **k: None)
    get_registry().repositories.clear()
    return root


def _source(tmp_path):
    return str(tmp_path / "data" / "papers")


def test_create_without_source_path_stays_created_and_lists():
    response = client.post("/repository/", json={"name": "test-repo", "branch": "main"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-repo"
    assert data["status"] == "CREATED"

    listing = client.get("/repository/")
    assert listing.status_code == 200
    assert [r["repo_id"] for r in listing.json()] == [data["repo_id"]]


def test_create_with_source_path_starts_indexing(tmp_path):
    response = client.post("/repository/", json={"name": "r", "source_path": _source(tmp_path)})
    assert response.status_code == 200
    assert response.json()["status"] == "INDEXING"


def test_status_and_update():
    repo_id = client.post("/repository/", json={"name": "test-repo-2", "branch": "develop"}).json()["repo_id"]

    status_resp = client.get(f"/repository/{repo_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "CREATED"

    update_resp = client.put(f"/repository/{repo_id}", json={"status": "READY", "name": "renamed"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "READY"
    assert update_resp.json()["name"] == "renamed"


def test_get_unknown_repository_is_404():
    assert client.get("/repository/does-not-exist").status_code == 404


def test_reindex_requires_source_path():
    repo_id = client.post("/repository/", json={"name": "no-src"}).json()["repo_id"]
    assert client.post(f"/repository/{repo_id}/reindex").status_code == 400


def test_reindex_and_delete(tmp_path):
    repo_id = client.post("/repository/", json={"name": "r3", "source_path": _source(tmp_path)}).json()["repo_id"]

    # Reset to a non-indexing state so reindex is accepted.
    client.put(f"/repository/{repo_id}", json={"status": "READY"})
    reindex_resp = client.post(f"/repository/{repo_id}/reindex")
    assert reindex_resp.status_code == 200
    assert client.get(f"/repository/{repo_id}/status").json()["status"] == "UPDATING"

    assert client.delete(f"/repository/{repo_id}").status_code == 200
    assert client.get("/repository/").json() == []
