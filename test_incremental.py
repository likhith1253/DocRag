import os
import shutil
import time
from storage.registry import RepositoryRegistry, Repository
from ingestion.worker import background_ingest_repository
from storage.snapshot import SnapshotManager
from storage.vector_store import VectorStoreManager
from storage.knowledge_graph import KnowledgeGraphManager

def setup_test_repo(repo_id: str) -> str:
    path = f"./test_repo_{repo_id}"
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    
    with open(os.path.join(path, "main.py"), "w") as f:
        f.write("def hello():\n    print('Hello World')\n\ndef bye():\n    print('Bye World')\n")
        
    with open(os.path.join(path, "utils.py"), "w") as f:
        f.write("def add(a, b):\n    return a + b\n")
        
    return path

def run_tests():
    print("=== INCREMENTAL INDEXING VALIDATION ===")
    
    registry = RepositoryRegistry("./test_registry.json")
    repo_id = "test_inc"
    path = setup_test_repo(repo_id)
    
    from storage.registry import RepoStatus
    repo = Repository(
        repo_id=repo_id, 
        name="Test Inc", 
        source_path=path,
        branch="main",
        vector_collection=f"col_{repo_id}",
        knowledge_graph=f"kg_{repo_id}",
        metadata=f"meta_{repo_id}",
        embedding_model="test",
        parser_version="1.0",
        status=RepoStatus.READY
    )
    registry.register(repo)
    
    # 1. Full Initial Ingest
    t0 = time.time()
    background_ingest_repository(repo_id, path, registry)
    t1 = time.time()
    
    sm = SnapshotManager()
    snap = sm.get_snapshot(repo_id)
    initial_file_count = len(snap.file_hashes)
    initial_chunk_count = sum(len(c) for c in snap.chunk_hashes.values())
    
    print(f"[Initial Ingest] Time: {t1-t0:.2f}s, Files: {initial_file_count}, Chunks: {initial_chunk_count}")
    
    initial_utils_hash = snap.file_hashes["utils.py"]
    
    # Scenario 1: Change one line (Modify file)
    with open(os.path.join(path, "utils.py"), "a") as f:
        f.write("def sub(a, b):\n    return a - b\n")
        
    t0 = time.time()
    background_ingest_repository(repo_id, path, registry)
    t1 = time.time()
    
    snap2 = sm.get_snapshot(repo_id)
    print(f"[Scenario 1: Modified] Time: {t1-t0:.2f}s, Speedup: {(t1-t0) / max(0.001, t1-t0):.1f}x")
    assert snap2.file_hashes["utils.py"] != initial_utils_hash
    
    # Scenario 2: Delete a file
    os.remove(os.path.join(path, "main.py"))
    
    t0 = time.time()
    background_ingest_repository(repo_id, path, registry)
    t1 = time.time()
    
    snap3 = sm.get_snapshot(repo_id)
    print(f"[Scenario 2: Deleted] Time: {t1-t0:.2f}s")
    assert "main.py" not in snap3.file_hashes
    
    # Verify Vector Store actually deleted chunks
    v_manager = VectorStoreManager(collection_name=repo.vector_collection)
    chunks = v_manager.get_all_chunks()
    # utils.py has 1 or 2 chunks, main.py is gone
    assert len(chunks) < initial_chunk_count
    
    print("✅ All Incremental Scenarios Passed!")
    
    # Clean up
    registry.delete_repository(repo_id)
    sm.delete_snapshot(repo_id)
    shutil.rmtree(path)
    
if __name__ == "__main__":
    run_tests()
