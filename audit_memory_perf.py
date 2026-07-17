import time
import psutil
import os
import uuid
import statistics
from fastapi.testclient import TestClient
from api.main import app
from storage.registry import RepositoryRegistry, Repository, RepoStatus

client = TestClient(app)

def get_mem():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def run_audit():
    print(f"Initial Memory: {get_mem():.2f} MB")
    
    # 1. Profile Indexing
    registry = RepositoryRegistry()
    
    # create repo
    t0 = time.time()
    res = client.post("/repository/", json={
        "name": "perf_test", 
        "branch": "main",
        "source_path": "./ingestion" # Just index the ingestion folder for speed
    })
    repo_id = res.json()["repo_id"]
    t1 = time.time()
    index_time = t1 - t0
    
    print(f"Indexing (async dispatch) Time: {index_time:.4f}s")
    print(f"Memory after Indexing Dispatch: {get_mem():.2f} MB")
    
    # We must actually run the worker synchronously to measure indexing memory
    from ingestion.worker import background_ingest_repository
    t0 = time.time()
    background_ingest_repository(repo_id, "./ingestion", registry)
    t1 = time.time()
    sync_index_time = t1 - t0
    print(f"Sync Indexing Time: {sync_index_time:.4f}s")
    print(f"Memory after Sync Indexing: {get_mem():.2f} MB")
    
    # 2. Profile Retrieval & Generation (P50, P95)
    latencies = []
    
    for i in range(10):
        t_start = time.time()
        # "How does chunking work?" - natural query for the ingestion folder
        res = client.post("/query", json={"question": f"How does chunking work? {i}", "repo_id": repo_id})
        t_end = time.time()
        latencies.append(t_end - t_start)
        
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    
    print(f"Memory after Queries: {get_mem():.2f} MB")
    print(f"Query P50: {p50:.4f}s")
    print(f"Query P95: {p95:.4f}s")
    
    # 3. Profile Caching
    t0 = time.time()
    res = client.post("/query", json={"question": "How does chunking work? 0", "repo_id": repo_id})
    t1 = time.time()
    cache_hit_time = t1 - t0
    print(f"Cache Hit Time: {cache_hit_time:.4f}s")

    with open("memory_perf_results.txt", "w") as f:
        f.write(f"Sync Indexing Time: {sync_index_time:.4f}s\n")
        f.write(f"Query P50: {p50:.4f}s\n")
        f.write(f"Query P95: {p95:.4f}s\n")
        f.write(f"Cache Hit Time: {cache_hit_time:.4f}s\n")
        f.write(f"Peak Memory: {get_mem():.2f} MB\n")

if __name__ == "__main__":
    run_audit()
