import json
import os
import sys
import glob
from collections import defaultdict
import csv

def run_error_analysis():
    print("="*60)
    print("Phase 8: Error Analysis")
    print("="*60)

    results_base = "eval/results"
    if not os.path.exists(results_base):
        print(f"Error: {results_base} not found.")
        sys.exit(1)

    exp_dirs = [os.path.join(results_base, d) for d in os.listdir(results_base) if d.startswith("main_comparison") and os.path.isdir(os.path.join(results_base, d))]
    if not exp_dirs:
        print("Error: No main_comparison experiment results found.")
        sys.exit(1)

    latest_exp = sorted(exp_dirs)[-1]
    raw_dir = os.path.join(latest_exp, "raw")
    
    jfile = os.path.join(raw_dir, "CodeGraphRAG.jsonl")
    if not os.path.exists(jfile):
        print(f"Error: {jfile} not found.")
        sys.exit(1)

    errors = []
    
    with open(jfile, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            res = json.loads(line)
            qid = res.get("question_id") or res.get("id")
            
            f1 = res.get("metrics", {}).get("token_f1", 0.0)
            r5 = res.get("metrics", {}).get("recall_at_5", 0.0)
            
            # If completely failed
            if f1 == 0.0:
                # Classify error
                if r5 == 0.0:
                    cat = "Retrieval Failure"
                else:
                    # Retrieved it, but failed to extract/answer
                    cat = "LLM Generation Failure / Hallucination"
                    
                errors.append({
                    "QuestionID": qid,
                    "ErrorCategory": cat,
                    "Recall@5": round(r5, 3),
                    "F1": round(f1, 3)
                })

    csv_path = "eval/error_analysis.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["QuestionID", "ErrorCategory", "Recall@5", "F1"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(errors)

    print(f"Error analysis completed. Found {len(errors)} completely failed questions.")
    print(f"Results saved to {csv_path}")

if __name__ == "__main__":
    run_error_analysis()
