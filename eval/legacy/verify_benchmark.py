import os
import sys
import json

def verify_benchmark(base_dir):
    dataset_path = "eval/benchmark_dataset.json"
    if not os.path.exists(dataset_path):
        print(f"Error: {dataset_path} not found.")
        sys.exit(1)
        
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    items = data.get("items", [])
    ids = set()
    for item in items:
        if item["id"] in ids:
            print(f"Error: Duplicate ID {item['id']}")
            sys.exit(1)
        ids.add(item["id"])
        
    print(f"Benchmark verified. {len(items)} unique items.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_benchmark.py <base_dir>")
        sys.exit(1)
    verify_benchmark(sys.argv[1])
