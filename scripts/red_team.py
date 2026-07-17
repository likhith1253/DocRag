import requests
import concurrent.futures
import time

API_URL = "http://localhost:8000"

def test_concurrency():
    print("Testing Concurrency (10 simultaneous queries)...")
    def make_query(i):
        try:
            start = time.time()
            res = requests.post(f"{API_URL}/query", json={"question": f"What is RAG? {i}", "collection_id": "RAG"})
            return res.status_code, time.time() - start
        except Exception as e:
            return str(e), 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_query, i) for i in range(10)]
        results = [f.result() for f in futures]
    
    success = sum(1 for r, _ in results if r == 200)
    print(f"Concurrency result: {success}/10 successful")
    if success < 10:
        print("Failed results:", [r for r, _ in results if r != 200])
    return success == 10

def test_empty_query():
    print("Testing Empty Query...")
    res = requests.post(f"{API_URL}/query", json={"question": "   ", "collection_id": "RAG"})
    print(f"Empty query status: {res.status_code} (Expected 400)")

def test_missing_collection():
    print("Testing Missing Collection...")
    res = requests.post(f"{API_URL}/query", json={"question": "Test", "collection_id": "DOES_NOT_EXIST"})
    print(f"Missing collection status: {res.status_code} (Expected 404 or gracefully handled)")

if __name__ == "__main__":
    test_empty_query()
    test_missing_collection()
    test_concurrency()
