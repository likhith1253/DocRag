import json
import os
import sys
import glob

def run_figures():
    print("="*60)
    print("Phase 9: Publication Figures")
    print("="*60)
    
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd
    except ImportError:
        print("[WARNING] matplotlib, seaborn, or pandas not installed. Skipping figure generation.")
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
    
    jsonl_files = glob.glob(os.path.join(raw_dir, "*.jsonl"))
    
    data = []
    for jfile in jsonl_files:
        sys_name = os.path.basename(jfile).replace(".jsonl", "")
        with open(jfile, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                res = json.loads(line)
                f1 = res.get("metrics", {}).get("token_f1", 0.0)
                r5 = res.get("metrics", {}).get("recall_at_5", 0.0)
                lat = res.get("metrics", {}).get("latency_s", 0.0)
                data.append({"System": sys_name, "F1": f1, "Recall@5": r5, "Latency": lat})
                
    df = pd.DataFrame(data)
    
    out_dir = "eval/figures"
    os.makedirs(out_dir, exist_ok=True)
    
    # Plot 1: F1 Boxplot
    plt.figure(figsize=(10, 6))
    sns.boxplot(x="System", y="F1", data=df)
    plt.title("F1 Score Distribution by System")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "f1_distribution.png"), dpi=300)
    plt.savefig(os.path.join(out_dir, "f1_distribution.pdf"))
    plt.close()
    
    # Plot 2: Recall@5 Boxplot
    plt.figure(figsize=(10, 6))
    sns.boxplot(x="System", y="Recall@5", data=df)
    plt.title("Recall@5 Distribution by System")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "recall_5_distribution.png"), dpi=300)
    plt.savefig(os.path.join(out_dir, "recall_5_distribution.pdf"))
    plt.close()

    print(f"Generated figures in {out_dir}")

if __name__ == "__main__":
    run_figures()
