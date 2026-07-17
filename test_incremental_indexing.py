import os
import sys
import time
import shutil
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, _PROJECT_ROOT)

from ingestion.worker import background_ingest_repository
from storage.registry import RepositoryRegistry, Repository, RepoStatus
from storage.snapshot import SnapshotManager

def test_incremental_indexing():
    """Test that only modified files are re-indexed with speed improvement."""
    print(f"\n{'='*60}")
    print(f"TEST: INCREMENTAL INDEXING")
    print(f"{'='*60}")
    
    # Create a temporary test repository
    test_repo_path = os.path.join(_PROJECT_ROOT, "test_repos", "TestRepo")
    if os.path.exists(test_repo_path):
        shutil.rmtree(test_repo_path)
    os.makedirs(test_repo_path)
    
    # Create initial files
    file1_path = os.path.join(test_repo_path, "file1.py")
    file2_path = os.path.join(test_repo_path, "file2.py")
    
    with open(file1_path, "w") as f:
        f.write("def function1():\n    return 'hello'\n")
    
    with open(file2_path, "w") as f:
        f.write("def function2():\n    return 'world'\n")
    
    repo_id = "TestRepo"
    
    # Clear snapshot for clean test
    snapshot_manager = SnapshotManager()
    try:
        snapshot_manager.delete_snapshot(repo_id)
        print(f"Cleared snapshot for {repo_id}")
    except:
        pass
    
    # Register repository
    registry = RepositoryRegistry()
    repo = Repository(
        repo_id=repo_id,
        name=repo_id,
        source_path=test_repo_path,
        branch="main",
        vector_collection=f"col_{repo_id}",
        knowledge_graph=f"{repo_id}_graph",
        metadata=f"{repo_id}_metadata",
        embedding_model="intfloat/e5-base-v2",
        parser_version="1.0",
        status=RepoStatus.READY,
        indexed_at=datetime.now(timezone.utc)
    )
    registry.register(repo)
    
    # RUN 1: Initial full indexing
    print(f"\n{'='*60}")
    print(f"RUN 1: INITIAL FULL INDEXING")
    print(f"{'='*60}")
    start_time = time.time()
    background_ingest_repository(repo_id, test_repo_path, registry)
    run1_duration = time.time() - start_time
    print(f"Run 1 duration: {run1_duration:.2f}s")
    
    # Modify one file
    print(f"\n{'='*60}")
    print(f"MODIFYING FILE1")
    print(f"{'='*60}")
    with open(file1_path, "w") as f:
        f.write("def function1():\n    return 'hello modified'\n")
    
    # RUN 2: Incremental indexing (should only process modified file)
    print(f"\n{'='*60}")
    print(f"RUN 2: INCREMENTAL INDEXING (SHOULD BE FASTER)")
    print(f"{'='*60}")
    start_time = time.time()
    background_ingest_repository(repo_id, test_repo_path, registry)
    run2_duration = time.time() - start_time
    print(f"Run 2 duration: {run2_duration:.2f}s")
    
    # Cleanup
    shutil.rmtree(test_repo_path)
    
    # Results
    print(f"\n{'='*60}")
    print(f"INCREMENTAL INDEXING RESULTS")
    print(f"{'='*60}")
    print(f"Run 1 (full indexing) duration: {run1_duration:.2f}s")
    print(f"Run 2 (incremental) duration: {run2_duration:.2f}s")
    print(f"Speedup: {run1_duration / run2_duration:.2f}x")
    
    if run2_duration < run1_duration:
        print(f"[PASS] Incremental indexing faster than full indexing")
        return True
    else:
        print(f"[FAIL] Incremental indexing not faster")
        return False

if __name__ == "__main__":
    result = test_incremental_indexing()
    sys.exit(0 if result else 1)
