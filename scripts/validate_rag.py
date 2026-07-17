import requests
import time
import os
import glob
import json

API_URL = "http://localhost:8000"
BASE_PAPERS_DIR = "d:/DocRag/papers"

COLLECTIONS = ["AI", "RAG", "LLM", "ComputerVision", "MedicalAI", "GraphML", "Robotics"]

QUERIES_TEMPLATES = {
    "RAG": [
        ("What is retrieval augmented generation?", True),
        ("What are the limitations of RAG systems?", True),
        ("What GPU was used for training?", False), # Likely not present or generic
        ("Who is the author of the most cited RAG paper?", False),
    ],
    "ComputerVision": [
        ("What datasets are used for evaluation?", True),
        ("Describe the model architecture.", True),
        ("What accuracy did GPT-10 achieve?", False), # Impossible
    ],
    "MedicalAI": [
        ("What medical applications are discussed?", True),
        ("What are the privacy concerns?", True),
        ("Which author recommends Python 5.0?", False), # Impossible
    ]
}

def register_collection(name, path):
    print(f"Registering collection '{name}' from {path}...")
    res = requests.post(f"{API_URL}/repository/", json={"name": name, "source_path": path})
    res.raise_for_status()
    data = res.json()
    repo_id = data["repo_id"]
    print(f"  -> Collection registered with ID: {repo_id}")
    return repo_id

def wait_for_indexing(repo_id):
    print(f"Waiting for indexing to complete for {repo_id}...")
    while True:
        try:
            res = requests.get(f"{API_URL}/indexing/status/{repo_id}")
            res.raise_for_status()
            status_data = res.json()
            stage = status_data.get("stage", "unknown")
            pct = status_data.get("percentage", 0)
            print(f"  [{stage}] {pct:.1f}%")
            if stage.lower() == "completed":
                print("  -> Indexing completed successfully.")
                return True
            if "error" in stage.lower() or "failed" in stage.lower():
                print(f"  -> Indexing failed: {stage}")
                return False
            time.sleep(2)
        except Exception as e:
            print(f"Error checking status: {e}")
            time.sleep(2)

def test_queries(repo_id, collection_name):
    queries = QUERIES_TEMPLATES.get(collection_name, [])
    if not queries:
        queries = [("What is the main contribution of this paper?", True),
                   ("What dataset was evaluated?", True),
                   ("What are the limitations?", True),
                   ("What accuracy did GPT-10 achieve?", False)]

    print(f"\\n--- Testing Queries for {collection_name} ---")
    results = []
    for q, is_possible in queries:
        print(f"Q: {q}")
        start_time = time.time()
        try:
            res = requests.post(f"{API_URL}/query", json={"question": q, "collection_id": repo_id})
            res.raise_for_status()
            data = res.json()
            answer = data.get("answer", "")
            citations = data.get("citations", [])
            latency = time.time() - start_time
            
            print(f"  Latency: {latency:.2f}s")
            print(f"  Answer preview: {answer[:100]}...")
            print(f"  Citations: {len(citations)}")
            
            # Grounding check
            if not is_possible:
                passed = "cannot find" in answer.lower()
                print(f"  [Negative Test] Passed: {passed}")
            else:
                passed = len(citations) > 0 and "cannot find" not in answer.lower()
                print(f"  [Positive Test] Passed: {passed}")
            
            results.append({
                "query": q,
                "is_possible": is_possible,
                "latency": latency,
                "citations_count": len(citations),
                "passed": passed
            })
        except Exception as e:
            print(f"  Error querying: {e}")
            results.append({
                "query": q,
                "is_possible": is_possible,
                "error": str(e),
                "passed": False
            })
    return results

def test_isolation(repo_id):
    print(f"\\n--- Testing Isolation ---")
    q = "What is a graph neural network?"
    print(f"Asking GraphML question to ComputerVision collection: '{q}'")
    try:
        res = requests.post(f"{API_URL}/query", json={"question": q, "collection_id": repo_id})
        res.raise_for_status()
        data = res.json()
        answer = data.get("answer", "")
        passed = "cannot find" in answer.lower()
        print(f"  [Isolation Test] Passed: {passed}")
        return passed
    except Exception as e:
        print(f"  Error in isolation test: {e}")
        return False

def run_validation():
    report = {"collections": {}, "isolation_passed": False}
    repo_ids = {}
    
    # 1. Index everything
    for col in COLLECTIONS:
        path = os.path.join(BASE_PAPERS_DIR, col)
        if not os.path.exists(path) or not os.listdir(path):
            print(f"Skipping empty or missing directory: {path}")
            continue
            
        repo_id = register_collection(col, path)
        success = wait_for_indexing(repo_id)
        if success:
            repo_ids[col] = repo_id
            report["collections"][col] = {"status": "indexed"}
        else:
            report["collections"][col] = {"status": "failed_indexing"}
            
    # 2. Validation Loop
    for col, repo_id in repo_ids.items():
        results = test_queries(repo_id, col)
        report["collections"][col]["queries"] = results
        
    # 3. Isolation Test
    if "ComputerVision" in repo_ids:
        report["isolation_passed"] = test_isolation(repo_ids["ComputerVision"])
        
    # Save Report
    with open("d:/DocRag/scripts/validation_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\\nValidation complete. Report saved to scripts/validation_report.json")

if __name__ == "__main__":
    # Ensure API is reachable before starting
    try:
        requests.get(f"{API_URL}/health")
    except Exception:
        print(f"Error: API not reachable at {API_URL}. Please start 'uvicorn api.main:app' first.")
        exit(1)
        
    run_validation()
