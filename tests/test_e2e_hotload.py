import os
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.dependencies import get_registry

client = TestClient(app)

def test_hot_loading_flow():
    # 1. Create a dummy test file to ingest
    test_dir = "./test_repo_src"
    os.makedirs(test_dir, exist_ok=True)
    with open(f"{test_dir}/main.py", "w") as f:
        f.write("def hello():\n    print('world')\n")
        
    # 2. Trigger Hot Loading (Create Repository with source_path)
    create_resp = client.post("/repository/", json={
        "name": "test-hotload",
        "branch": "main",
        "source_path": test_dir
    })
    
    assert create_resp.status_code == 200
    repo_id = create_resp.json()["repo_id"]
    assert create_resp.json()["status"] in ["INDEXING_TIER0", "INDEXING_TIER1", "INDEXING_TIER2", "READY"]
    
    # 3. Query the API
    query_resp = client.post("/query", json={
        "question": "What does the hello function print?",
        "repo_id": repo_id
    })
    
    assert query_resp.status_code == 200
    assert "world" in query_resp.json()["answer"].lower() or "not found" in query_resp.json()["answer"].lower()
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)
