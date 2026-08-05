import os
import sys
import time

sys.path.insert(0, r"d:\DocRag")
from agents.orchestrator import answer

question = "How does the paper address contradictions in NLP tasks?"
repo_id = "71e2cffe-8756-4ff3-b35c-52fc94babdd4"

print("==================================================")
print(f"STARTING 20 SEQUENTIAL RUNS FOR INTERMITTENT FAILURE INVESTIGATION")
print(f"Question: {question}")
print(f"Repo ID: {repo_id}")
print("==================================================\n")

results = []

for i in range(1, 21):
    t0 = time.perf_counter()
    ans, bd, chunks, citations = answer(
        query=question,
        repo_id=repo_id,
        filters={},
        retrieval_mode="single"
    )
    t1 = time.perf_counter()
    elapsed_sec = t1 - t0
    
    # Check if answer is fallback or valid
    is_fallback = "cannot find" in ans.lower() or len(chunks) == 0
    status = "FAIL" if is_fallback else "PASS"
    
    first_failing = "NONE"
    if is_fallback:
        try:
            summary_path = r"d:\DocRag\.debug\current_query\summary.txt"
            if os.path.exists(summary_path):
                with open(summary_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("First Failing Stage"):
                            first_failing = line.split(":", 1)[1].strip()
                        elif line.startswith("Root Cause"):
                            first_failing += f" | {line.split(':', 1)[1].strip()}"
        except Exception as e:
            first_failing = f"Error reading summary: {e}"

    res = {
        "run": i,
        "status": status,
        "latency_s": round(elapsed_sec, 2),
        "chunks": len(chunks),
        "citations": len(citations),
        "first_failing": first_failing,
        "ans_preview": ans[:80].replace("\n", " ")
    }
    results.append(res)
    print(f"Run {i:2d}: [{status}] in {elapsed_sec:.2f}s | Chunks: {len(chunks)} | Citations: {len(citations)} | FirstFailing: {first_failing}")

print("\n==================================================")
print("INVESTIGATION RUN SUMMARY")
print("==================================================")
passes = sum(1 for r in results if r["status"] == "PASS")
fails = sum(1 for r in results if r["status"] == "FAIL")
print(f"Total Runs: 20 | PASS: {passes} | FAIL: {fails}")
for r in results:
    print(f"Run {r['run']:2d}: [{r['status']}] {r['latency_s']}s - {r['ans_preview']}...")
