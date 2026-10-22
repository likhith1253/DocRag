import os
import sys
import json
import hashlib
import platform

def compute_hash(filepath):
    if not os.path.exists(filepath): return None
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def verify_environment(base_dir):
    manifest = {
        "python_version": platform.python_version(),
        "os": platform.platform(),
        "benchmark_checksum": compute_hash("eval/benchmark_dataset.json"),
        "config_hash": compute_hash("config.yaml"),
        "timestamp": os.path.basename(base_dir).split("_", 1)[1] if "_" in os.path.basename(base_dir) else "unknown"
    }
    
    # Write manifest
    man_path = os.path.join(base_dir, "experiment_manifest.json")
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"Environment verified. Manifest written to {man_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify_environment.py <base_dir>")
        sys.exit(1)
    verify_environment(sys.argv[1])
