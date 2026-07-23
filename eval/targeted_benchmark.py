"""
Targeted benchmark for the 14 failing questions.
Measures: Accuracy (answer!=CANNOT_FIND), Retrieval Recall@K, Concept Coverage,
Duplicate %, Context Precision, Chunk Utilization, Latency.
Run from d:/DocRag:
  python eval/targeted_benchmark.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import json, time

DIAGNOSIS_PATH = "eval/results/diagnosis.json"
CANNOT_FIND = "I cannot find this information in the uploaded documents."

with open("eval/ai_papers_expected_answers.json", encoding="utf-8") as f:
    expected_list = json.load(f)
expected = {e["id"]: e for e in expected_list}

with open(DIAGNOSIS_PATH, encoding="utf-8") as f:
    diagnosis = json.load(f)

def concept_coverage(key_concepts, text):
    if not key_concepts: return 0.0
    t = text.lower()
    return sum(1 for kc in key_concepts if kc.lower() in t) / len(key_concepts)

results = []
print("="*70)
print("TARGETED BENCHMARK — 14 questions (post-fix)")
print("="*70)

from storage.registry import get_registry
from agents.orchestrator import answer
registry = get_registry()

# Build paper->repo_id map by scanning chunks
paper_to_repo = {}
for rid, repo in registry.repositories.items():
    if repo.status in ("READY", "INDEXING_TIER1", "INDEXING_TIER2"):
        try:
            from storage.vector_store import VectorStoreManager
            vm = VectorStoreManager(collection_name=repo.vector_collection)
            chunks = vm.get_all_chunks()
            for c in chunks:
                fn = os.path.basename(c.get("metadata", {}).get("file", ""))
                if fn and fn not in paper_to_repo:
                    paper_to_repo[fn] = rid
        except Exception:
            continue

print(f"Found {len(paper_to_repo)} papers across {len(registry.repositories)} repos")

for q_item in diagnosis:
    qid = q_item["id"]
    question = q_item["question"]
    paper = q_item["paper"]
    key_concepts = q_item["key_concepts"]

    print(f"\n[{qid}] {question[:80]}...")

    repo_id = paper_to_repo.get(paper)
    t0 = time.time()
    ans_text, latency_bd = answer(question, repo_id=repo_id)
    latency = time.time() - t0

    # Read last log entry for chunk details
    chunks_retrieved = []
    logs_path = "logs/query_logs.jsonl"
    if os.path.exists(logs_path):
        with open(logs_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if lines:
            try:
                last = json.loads(lines[-1])
                if last.get("question") == question:
                    chunks_retrieved = last.get("retrieved_chunks", [])
            except Exception:
                pass

    answered = ans_text.strip() != CANNOT_FIND and len(ans_text.strip()) > 20
    retrieved_text = " ".join(c.get("content","") for c in chunks_retrieved)
    retrieval_recall = concept_coverage(key_concepts, retrieved_text)
    answer_cov = concept_coverage(key_concepts, ans_text)

    hashes = [c.get("metadata",{}).get("hash","") for c in chunks_retrieved]
    dup_pct = (1 - len(set(hashes))/max(1, len(hashes))) * 100 if hashes else 0.0

    cited = sum(1 for i in range(1, len(chunks_retrieved)+1)
                if f"[Excerpt {i}]" in ans_text or f"Excerpt {i}" in ans_text)
    utilization = cited / max(1, len(chunks_retrieved))

    print(f"  Answered:         {answered}")
    print(f"  Answer[:150]:     {ans_text[:150]}")
    print(f"  Retrieval Recall: {retrieval_recall:.2%}  Answer Coverage: {answer_cov:.2%}")
    print(f"  Chunks: {len(chunks_retrieved)}  Dup%: {dup_pct:.1f}%  Util: {utilization:.2%}  Lat: {latency:.2f}s")

    results.append({
        "id": qid, "question": question, "paper": paper,
        "answered": answered, "answer": ans_text[:500],
        "retrieval_recall": retrieval_recall, "answer_coverage": answer_cov,
        "chunks_retrieved": len(chunks_retrieved),
        "duplicate_pct": dup_pct, "chunk_utilization": utilization,
        "latency_s": round(latency, 3),
    })

n = len(results)
accuracy = sum(r["answered"] for r in results) / max(1, n)
avg_recall = sum(r["retrieval_recall"] for r in results) / max(1, n)
avg_ans_cov = sum(r["answer_coverage"] for r in results) / max(1, n)
avg_lat = sum(r["latency_s"] for r in results) / max(1, n)
avg_dup = sum(r["duplicate_pct"] for r in results) / max(1, n)
avg_util = sum(r["chunk_utilization"] for r in results) / max(1, n)

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"  Accuracy (answered):      {accuracy:.2%}  ({sum(r['answered'] for r in results)}/{n})")
print(f"  Retrieval Recall (avg):   {avg_recall:.2%}")
print(f"  Answer Coverage (avg):    {avg_ans_cov:.2%}")
print(f"  Avg Latency:              {avg_lat:.2f}s")
print(f"  Avg Duplicate %:          {avg_dup:.1f}%")
print(f"  Avg Chunk Utilization:    {avg_util:.2%}")
print("="*70)

os.makedirs("eval/results", exist_ok=True)
out_path = "eval/results/targeted_benchmark_post_fix.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"summary": {
        "accuracy": accuracy, "retrieval_recall": avg_recall,
        "answer_coverage": avg_ans_cov, "latency_s": avg_lat,
        "duplicate_pct": avg_dup, "chunk_utilization": avg_util,
        "n_answered": sum(r["answered"] for r in results), "n_total": n
    }, "per_question": results}, f, indent=2, ensure_ascii=False)
print(f"\nResults saved to {out_path}")
