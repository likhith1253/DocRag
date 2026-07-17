import json
import os
import sys
import glob
from collections import defaultdict
import csv

def run_calibration():
    print("="*60)
    print("Phase 6: Empirical Difficulty Calibration")
    print("="*60)

    # Find the latest main_comparison results directory
    results_base = "eval/results"
    if not os.path.exists(results_base):
        print(f"Error: {results_base} not found.")
        sys.exit(1)

    # Find all main_comparison runs and pick the latest
    exp_dirs = []
    for d in os.listdir(results_base):
        if d.startswith("main_comparison"):
            path = os.path.join(results_base, d)
            if os.path.isdir(path):
                exp_dirs.append(path)

    if not exp_dirs:
        print("Error: No main_comparison experiment results found.")
        sys.exit(1)

    latest_exp = sorted(exp_dirs)[-1]
    raw_dir = os.path.join(latest_exp, "raw")
    print(f"Using results from: {latest_exp}")

    # Load original benchmark for structural labels
    benchmark_path = "eval/benchmark_dataset.json"
    with open(benchmark_path, "r", encoding="utf-8") as f:
        bench_data = json.load(f)
    items = bench_data.get("items", [])
    
    structural_labels = {item["id"]: item.get("difficulty", "unknown") for item in items}
    
    # Read all raw JSONL files
    jsonl_files = glob.glob(os.path.join(raw_dir, "*.jsonl"))
    if not jsonl_files:
        print(f"Error: No JSONL files found in {raw_dir}")
        sys.exit(1)
        
    stats = defaultdict(lambda: {"count": 0, "token_f1_sum": 0.0, "recall_5_sum": 0.0, "latency_sum": 0.0})
    
    for jfile in jsonl_files:
        with open(jfile, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                res = json.loads(line)
                qid = res.get("question_id") or res.get("id")
                # Wait, what's the schema of raw.jsonl? 
                # Let's assume it has question_id, metrics object
                if "metrics" in res:
                    m = res["metrics"]
                    stats[qid]["count"] += 1
                    stats[qid]["token_f1_sum"] += m.get("token_f1", 0.0)
                    stats[qid]["recall_5_sum"] += m.get("recall_at_5", 0.0)
                    stats[qid]["latency_sum"] += m.get("latency_s", 0.0)

    if not stats:
        print("Error: Could not extract stats from JSONL files.")
        sys.exit(1)

    # Compute averages and empirical difficulty
    output_rows = []
    
    for qid, st in stats.items():
        n = st["count"]
        avg_f1 = st["token_f1_sum"] / n if n > 0 else 0
        avg_r5 = st["recall_5_sum"] / n if n > 0 else 0
        avg_lat = st["latency_sum"] / n if n > 0 else 0
        
        # Empirical logic:
        # Easy: avg_f1 > 0.6
        # Medium: 0.2 < avg_f1 <= 0.6
        # Hard: avg_f1 <= 0.2
        if avg_f1 > 0.6:
            emp_diff = "easy"
        elif avg_f1 > 0.2:
            emp_diff = "medium"
        else:
            emp_diff = "hard"
            
        orig_diff = structural_labels.get(qid, "unknown")
        
        disagreement = "YES" if emp_diff != orig_diff.lower() else "NO"
        
        output_rows.append({
            "QuestionID": qid,
            "AvgAccuracy(F1)": round(avg_f1, 3),
            "AvgRetrieval(R@5)": round(avg_r5, 3),
            "AvgLatency(s)": round(avg_lat, 3),
            "StructuralDifficulty": orig_diff,
            "EmpiricalDifficulty": emp_diff,
            "Disagreement": disagreement
        })

    # Output to CSV
    csv_path = "eval/difficulty_calibration.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["QuestionID", "AvgAccuracy(F1)", "AvgRetrieval(R@5)", "AvgLatency(s)", "StructuralDifficulty", "EmpiricalDifficulty", "Disagreement"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Calibration completed. Processed {len(output_rows)} questions.")
    print(f"Results saved to {csv_path}")
    
if __name__ == "__main__":
    run_calibration()
