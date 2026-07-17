import os
import sys
import time
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, _PROJECT_ROOT)

from ingestion.worker import background_ingest_repository
from storage.registry import RepositoryRegistry, Repository, RepoStatus
from storage.snapshot import SnapshotManager
from storage.vector_store import VectorStoreManager

def test_progressive_indexing():
    """Test that Tier0, Tier1, Tier2, READY occur in correct order."""
    print(f"\n{'='*60}")
    print(f"TEST: PROGRESSIVE INDEXING ORDER")
    print(f"{'='*60}")
    
    pydantic_path = os.path.join(_PROJECT_ROOT, "test_repos", "smalltest")
    repo_id = "smalltest"
    
    # Clear snapshot only (don't clear collection - let it handle itself)
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
        source_path=pydantic_path,
        branch="main",
        vector_collection=f"col_{repo_id}",
        knowledge_graph=f"{repo_id}_graph",
        metadata=f"{repo_id}_metadata",
        embedding_model="intfloat/e5-base-v2",
        parser_version="1.0",
        status=RepoStatus.READY,
        indexed_at=datetime.now(timezone.utc)
    )
    
    # Track status transitions
    status_transitions = []
    
    def monitor_status():
        """Monitor status changes during ingestion."""
        last_status = None
        for _ in range(2000): # Monitor for up to 2000 iterations (longer)
            current_repo = registry.get_repository(repo_id)
            if current_repo:
                current_status = current_repo.status
                if current_status != last_status:
                    status_transitions.append((current_status, datetime.now(timezone.utc)))
                    last_status = current_status
                    print(f"Status transition: {current_status} at {datetime.now(timezone.utc).isoformat()}")
                    # Stop if we reach READY
                    if current_status == RepoStatus.READY and len(status_transitions) > 1:
                        break
            time.sleep(0.05) # Check every 50ms for faster response
    
    # Start monitoring in background BEFORE registering the repo!
    import threading
    monitor_thread = threading.Thread(target=monitor_status)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Now register the repo so monitor can pick up initial state!
    registry.register(repo)
    
    # Run ingestion
    print(f"\n{'='*60}")
    print(f"RUNNING INGESTION")
    print(f"{'='*60}")
    background_ingest_repository(repo_id, pydantic_path, registry)
    
    # Wait for monitor to finish (give it more time for full completion)
    monitor_thread.join(timeout=120)
    
    # Additional check for final READY state
    final_repo = registry.get_repository(repo_id)
    if final_repo and final_repo.status == RepoStatus.READY:
        if RepoStatus.READY not in [s for s, _ in status_transitions]:
            status_transitions.append((RepoStatus.READY, datetime.now(timezone.utc)))
            print(f"Final READY state detected")
    
    # Verify status transitions
    print(f"\n{'='*60}")
    print(f"STATUS TRANSITIONS")
    print(f"{'='*60}")
    for status, timestamp in status_transitions:
        print(f"{status}: {timestamp.isoformat()}")
    
    # Check for correct order (ignore initial READY state)
    expected_order = [
        RepoStatus.INDEXING_TIER0,
        RepoStatus.INDEXING_TIER1,
        RepoStatus.INDEXING_TIER2,
        RepoStatus.READY
    ]
    
    # Extract statuses in order, skipping initial READY if present
    actual_statuses = [s for s, _ in status_transitions]
    if actual_statuses and actual_statuses[0] == RepoStatus.READY:
        actual_statuses = actual_statuses[1:]  # Skip initial READY
    
    print(f"\n{'='*60}")
    print(f"VERIFICATION")
    print(f"{'='*60}")
    print(f"Expected order: {expected_order}")
    print(f"Actual order (after initial READY): {actual_statuses}")
    
    # Check if all expected statuses appear in correct order
    status_positions = {}
    for status in expected_order:
        if status in actual_statuses:
            status_positions[status] = actual_statuses.index(status)
    
    if len(status_positions) == len(expected_order):
        # Verify order
        positions = list(status_positions.values())
        if positions == sorted(positions):
            print(f"[PASS] Progressive indexing stages occur in correct order")
            return True
        else:
            print(f"[FAIL] Status transitions out of order")
            return False
    else:
        print(f"[FAIL] Missing status transitions")
        print(f"Missing: {set(expected_order) - set(actual_statuses)}")
        return False

if __name__ == "__main__":
    result = test_progressive_indexing()
    sys.exit(0 if result else 1)
