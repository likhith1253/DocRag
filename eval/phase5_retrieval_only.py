import json
import os
import sys
import time
from typing import List, Dict, Any
from eval.benchmark.dataset import BenchmarkDataset
from eval.benchmark.systems.codegraphrag import CodeGraphRAGSystem

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def compute_recall_at_k(retrieved: List[str], ground_truth: List[str], k: int) -> float:
    if not ground_truth:
        return 1.0 # Vacuously true if no ground truth
    retrieved_k = set(retrieved[:k])
    gt_set = set(ground_truth)
    hits = len(retrieved_k.intersection(gt_set))
    return hits / len(gt_set)

def compute_mrr(retrieved: List[str], ground_truth: List[str]) -> float:
    if not ground_truth:
        return 1.0
    gt_set = set(ground_truth)
    for i, r in enumerate(retrieved):
        if r in gt_set:
            return 1.0 / (i + 1)
    return 0.0

def run_retrieval_only():
    print("="*60)
    print("Phase 5: Retrieval-only Validation")
    print("="*60)
    
    dataset_path = "eval/benchmark_dataset.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = data.get("items", [])
    
    system = CodeGraphRAGSystem({})
    system.warm_up()
    
    results = {
        "single-hop": {"count": 0, "r1": 0, "r5": 0, "r10": 0, "mrr": 0},
        "multi-hop": {"count": 0, "r1": 0, "r5": 0, "r10": 0, "mrr": 0}
    }
    
    print(f"Running retrieval for {len(items)} items...")
    
    for idx, item in enumerate(items):
        q = item["question"]
        gt = item.get("ground_truth_retrieval_chunks", [])
        
        # Determine hop category from complexity
        comp = item.get("retrieval_complexity", "").lower()
        if "single" in comp or "single-hop" in comp:
            cat = "single-hop"
        else:
            cat = "multi-hop"
            
        retrieved_chunks = system.retrieve(q, top_k=10)
        retrieved_files = [c.file_path for c in retrieved_chunks]
        
        # Ground truth is source files, not chunks
        gt = []
        if item.get("primary_source_file"):
            gt.append(item["primary_source_file"])
        if item.get("supporting_source_files"):
            gt.extend(item["supporting_source_files"])
        
        if gt:
            r1 = compute_recall_at_k(retrieved_files, gt, 1)
            r5 = compute_recall_at_k(retrieved_files, gt, 5)
            r10 = compute_recall_at_k(retrieved_files, gt, 10)
            mrr = compute_mrr(retrieved_files, gt)
        else:
            # If no GT chunks, we can't accurately measure chunk recall.
            # In our benchmark, some items might just have line ranges. 
            # We'll skip chunk precision if GT chunks are completely empty.
            r1 = r5 = r10 = mrr = 0.0
            if len(item.get("evidence_line_ranges", {})) > 0:
                pass # Line range overlap logic belongs in evaluator, we approximate here
                
        results[cat]["count"] += 1
        results[cat]["r1"] += r1
        results[cat]["r5"] += r5
        results[cat]["r10"] += r10
        results[cat]["mrr"] += mrr
        
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(items)}")
            
    # Compute averages
    for cat in results:
        count = results[cat]["count"]
        if count > 0:
            for metric in ["r1", "r5", "r10", "mrr"]:
                results[cat][metric] /= count
                
    print("\nRetrieval-Only Validation Results:")
    for cat in ["single-hop", "multi-hop"]:
        print(f"  {cat.upper()} ({results[cat]['count']} questions):")
        print(f"    Recall@1 : {results[cat]['r1']:.3f}")
        print(f"    Recall@5 : {results[cat]['r5']:.3f}")
        print(f"    Recall@10: {results[cat]['r10']:.3f}")
        print(f"    MRR      : {results[cat]['mrr']:.3f}")
        
    out_path = "eval/retrieval_only_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")

if __name__ == "__main__":
    run_retrieval_only()
