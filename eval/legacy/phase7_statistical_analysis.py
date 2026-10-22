import json
import os
import sys
import glob
from collections import defaultdict
import csv
import math

def run_statistical_analysis():
    print("="*60)
    print("Phase 7: Statistical Analysis")
    print("="*60)

    try:
        from scipy.stats import wilcoxon
        import numpy as np
    except ImportError:
        print("[WARNING] scipy or numpy not installed. Skipping advanced statistical tests.")
        return

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
    
    # Read scores per system per question
    # system -> question_id -> f1_score
    scores = defaultdict(dict)
    
    jsonl_files = glob.glob(os.path.join(raw_dir, "*.jsonl"))
    for jfile in jsonl_files:
        sys_name = os.path.basename(jfile).replace(".jsonl", "")
        with open(jfile, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                res = json.loads(line)
                qid = res.get("question_id") or res.get("id")
                if "metrics" in res:
                    f1 = res["metrics"].get("token_f1", 0.0)
                    scores[sys_name][qid] = f1

    if "CodeGraphRAG" not in scores:
        print("Error: Target system 'CodeGraphRAG' not found in raw results.")
        sys.exit(1)

    cg_scores = scores["CodeGraphRAG"]
    qids = sorted(list(cg_scores.keys()))
    
    if not qids:
        print("No questions found.")
        sys.exit(1)

    output_rows = []
    
    for sys_name, sys_scores in scores.items():
        if sys_name == "CodeGraphRAG":
            continue
            
        x = [cg_scores.get(q, 0.0) for q in qids]
        y = [sys_scores.get(q, 0.0) for q in qids]
        
        diffs = [a - b for a, b in zip(x, y)]
        mean_diff = np.mean(diffs)
        std_diff = np.std(diffs, ddof=1) if len(diffs) > 1 else 0
        
        # 95% CI for the mean difference
        n = len(diffs)
        if std_diff > 0 and n > 1:
            margin = 1.96 * (std_diff / math.sqrt(n))
            ci_lower = mean_diff - margin
            ci_upper = mean_diff + margin
        else:
            ci_lower = ci_upper = mean_diff
            
        # Wilcoxon signed-rank test
        try:
            # wilcoxon fails if all differences are zero
            if any(d != 0 for d in diffs):
                stat, p_value = wilcoxon(x, y)
            else:
                p_value = 1.0
        except Exception:
            p_value = 1.0
            
        # Cohen's d for paired samples: mean_diff / std_diff
        cohens_d = (mean_diff / std_diff) if std_diff > 0 else 0.0
        
        # Bonferroni correction for multiple comparisons
        # alpha = 0.05 / number of baselines
        num_baselines = len(scores) - 1
        alpha = 0.05 / max(1, num_baselines)
        significant = "YES" if p_value < alpha else "NO"

        output_rows.append({
            "Baseline": sys_name,
            "MeanDiff(F1)": round(mean_diff, 3),
            "95%CI": f"[{ci_lower:.3f}, {ci_upper:.3f}]",
            "P-Value": f"{p_value:.2e}",
            "CohensD": round(cohens_d, 3),
            "Significant(Bonferroni)": significant
        })

    csv_path = "eval/statistical_analysis.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["Baseline", "MeanDiff(F1)", "95%CI", "P-Value", "CohensD", "Significant(Bonferroni)"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Statistical analysis completed against {len(output_rows)} baselines.")
    print(f"Results saved to {csv_path}")

if __name__ == "__main__":
    run_statistical_analysis()
