import os
import sys
import uuid
import time
import json
import subprocess
from datetime import datetime
import shutil
import hashlib

def run_cmd(cmd, desc):
    print(f"\n[ORCHESTRATOR] {desc}")
    print(f"Executing: {' '.join(cmd)}")
    start = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start
    if res.returncode != 0:
        print(f"[FATAL] Task failed with exit code {res.returncode}")
        print(f"Stdout:\n{res.stdout}")
        print(f"Stderr:\n{res.stderr}")
        sys.exit(res.returncode)
    print(f"[SUCCESS] Completed in {elapsed:.2f}s")
    return res.stdout

def compute_hash(filepath):
    if not os.path.exists(filepath): return "missing"
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

import argparse

def main():
    parser = argparse.ArgumentParser(description="Final Autonomous Research Verification Loop")
    parser.add_argument("--resume", type=str, help="Resume an existing experiment from the specified base directory")
    parser.add_argument("--limit", type=int, help="Limit number of queries (for pilot runs)")
    args = parser.parse_args()

    print("="*80)
    print("FINAL AUTONOMOUS RESEARCH VERIFICATION LOOP")
    print("="*80)
    
    if args.resume:
        base_dir = args.resume
        if not os.path.exists(base_dir):
            print(f"[FATAL] Resume directory does not exist: {base_dir}")
            sys.exit(1)
        print(f"[RESUME] Resuming experiment in directory: {base_dir}")
    else:
        # Create immutable experiment directory
        from datetime import timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        exp_uuid = str(uuid.uuid4())
        base_dir = f"eval/results/experiment_{timestamp}_{exp_uuid[:8]}"
        os.makedirs(base_dir, exist_ok=False)
    
    # 1. Environment & Benchmark Verification
    run_cmd([sys.executable, "eval/verify_environment.py", base_dir], "Section A: Environment Integrity")
    run_cmd([sys.executable, "eval/verify_benchmark.py", base_dir], "Section B: Benchmark Integrity")
    
    # 2. Execute Main Comparison & Ablations (Store raw outputs immutably)
    # Note: run_experiment.py will be configured to output to base_dir
    main_cmd = [sys.executable, "eval/run_experiment.py", "--config", "eval/experiments/main_comparison.yaml", "--out_dir", base_dir]
    abl_cmd = [sys.executable, "eval/run_experiment.py", "--config", "eval/experiments/embedding_ablation.yaml", "--out_dir", base_dir]
    if args.limit:
        main_cmd.extend(["--limit", str(args.limit)])
        abl_cmd.extend(["--limit", str(args.limit)])
    
    run_cmd(main_cmd, "Section C: Main Comparison")
    run_cmd(abl_cmd, "Section C: Embedding Ablation")
    
    # 3. Independent Metric Reconstruction & Sanity Checks
    run_cmd([sys.executable, "eval/independent_auditor.py", base_dir], "Section E-N: Independent Verification & Reporting")
    
    # 4. Reproducibility Verification
    print("\n[ORCHESTRATOR] Section G: Reproducibility Verification")
    figures_dir = os.path.join(base_dir, "figures")
    metrics_csv = os.path.join(base_dir, "metrics.csv")
    
    if os.path.exists(figures_dir): shutil.rmtree(figures_dir)
    if os.path.exists(metrics_csv): os.remove(metrics_csv)
    
    run_cmd([sys.executable, "eval/independent_auditor.py", base_dir], "Regenerating all metrics and figures from RAW LOGS")
    
    if not os.path.exists(metrics_csv):
        print("[FATAL] Regenerated outputs missing. Reproducibility failed.")
        sys.exit(1)
        
    print("[SUCCESS] Research Readiness Loop Complete. Repository entering Research Freeze.")
    
if __name__ == "__main__":
    main()
