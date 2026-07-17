from fastapi.testclient import TestClient
from api.main import app
from storage.registry import RepoStatus
from api.dependencies import get_registry

client = TestClient(app)

def test_create_and_list_repository():
    # Clear registry for clean test
    registry = get_registry()
    registry.repositories.clear()
    
    response = client.post("/repository/", json={
        "name": "test-repo",
        "branch": "main",
        "language": "python"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-repo"
    assert data["status"] == "INDEXING"
    
    repo_id = data["repo_id"]
    
    # List should return 1 repo
    list_response = client.get("/repository/")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["repo_id"] == repo_id
    
def test_status_and_update():
    registry = get_registry()
    registry.repositories.clear()
    
    create_resp = client.post("/repository/", json={
        "name": "test-repo-2",
        "branch": "develop"
    })
    repo_id = create_resp.json()["repo_id"]
    
    # Get status
    status_resp = client.get(f"/repository/{repo_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "READY"
    
    # Update repository
    update_resp = client.put(f"/repository/{repo_id}", json={
        "status": "READY"
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "READY"
    
def test_reindex_and_delete():
    registry = get_registry()
    registry.repositories.clear()
    
    create_resp = client.post("/repository/", json={
        "name": "test-repo-3",
        "branch": "main"
    })
    repo_id = create_resp.json()["repo_id"]
    
    reindex_resp = client.post(f"/repository/{repo_id}/reindex")
    assert reindex_resp.status_code == 200
    
    # Status should be UPDATING
    status_resp = client.get(f"/repository/{repo_id}/status")
    assert status_resp.json()["status"] == "READY"
    
    # Delete
    del_resp = client.delete(f"/repository/{repo_id}")
    assert del_resp.status_code == 200
    
    # List should be empty
    list_resp = client.get("/repository/")
    assert len(list_resp.json()) == 0
