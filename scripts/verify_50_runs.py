"""
verify_50_runs.py
-----------------
Automated 50-Query Sequential Reliability & Stability Test Suite.

Verifies:
  1. 50/50 queries complete without exceptions.
  2. 0 queries return silent fallbacks or prompt cache hits.
  3. 0 Qdrant file-locking or memory access errors occur.
  4. 100% of queries execute full retrieval -> cross-encoder -> prompt assembly -> live LLM generation.
"""

import os
import sys
import time
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Ensure prompt cache is disabled so every call hits live inference
os.environ["ENABLE_PROMPT_CACHE"] = "0"
os.environ["DISABLE_PROMPT_CACHE"] = "1"

EVAL_FILE = ROOT / "eval" / "dataset" / "ai_papers.json"
AI_PAPERS_REPO_ID = None


def run_50_query_verification():
    from agents.orchestrator import answer as orchestrator_answer

    if not EVAL_FILE.exists():
        print(f"[ERROR] Benchmark dataset not found at: {EVAL_FILE}", flush=True)
        sys.exit(1)

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Repeat dataset to get 50 queries
    query_queue = []
    while len(query_queue) < 50:
        query_queue.extend(questions)
    query_queue = query_queue[:50]

    print("=" * 80, flush=True)
    print(f"DOCUMENTRAG 50-QUERY SEQUENTIAL RELIABILITY VERIFICATION", flush=True)
    print(f"Total Queries: {len(query_queue)}", flush=True)
    print(f"Collection ID: {AI_PAPERS_REPO_ID}", flush=True)
    print("=" * 80, flush=True)

    results = []
    passed_count = 0
    total_time = 0.0

    for idx, item in enumerate(query_queue, start=1):
        qid = item.get("id", f"Q{idx}")
        question = item["question"]
        target_paper = item.get("paper", "Unknown")

        print(f"\n[{idx}/50] Executing Query '{qid}'...", flush=True)
        print(f"  Question: {question[:75]}...", flush=True)
        t0 = time.perf_counter()

        try:
            ans, latency_bd, chunks, citations = orchestrator_answer(
                query=question,
                repo_id=AI_PAPERS_REPO_ID,
                filters={},
                retrieval_mode="single",
                request_id=f"verify50_{idx}_{qid}",
            )
            elapsed = time.perf_counter() - t0
            total_time += elapsed

            is_fallback = "i cannot find this information" in str(ans).lower()
            is_fast_cache = elapsed < 0.4  # < 400ms implies skipped generation / cache

            if is_fallback or is_fast_cache or not ans or str(ans).startswith("[ERROR]"):
                status = "FAIL"
                fail_reason = "Fallback Response" if is_fallback else ("Cached Fast-Return" if is_fast_cache else "Empty/Error Output")
            else:
                status = "PASS"
                fail_reason = "NONE"
                passed_count += 1

            record = {
                "run": idx,
                "qid": qid,
                "paper": target_paper,
                "latency_sec": round(elapsed, 2),
                "chunks_retrieved": len(chunks),
                "citations_count": len(citations),
                "llm_ms": round(latency_bd.get("llm_ms", 0.0), 2),
                "status": status,
                "reason": fail_reason,
            }
            results.append(record)

            print(
                f"  Result: {status} | Latency: {elapsed:.2f}s (LLM: {latency_bd.get('llm_ms', 0):.0f}ms) | "
                f"Chunks: {len(chunks)} | Citations: {len(citations)}",
                flush=True,
            )

        except Exception as e:
            elapsed = time.perf_counter() - t0
            print(f"  Result: CRASH ({e})", flush=True)
            results.append({
                "run": idx,
                "qid": qid,
                "paper": target_paper,
                "latency_sec": round(elapsed, 2),
                "chunks_retrieved": 0,
                "citations_count": 0,
                "llm_ms": 0.0,
                "status": "CRASH",
                "reason": str(e),
            })

    print("\n" + "=" * 80, flush=True)
    print("50-QUERY RELIABILITY VERIFICATION SUMMARY", flush=True)
    print("=" * 80, flush=True)
    print(f"Passed: {passed_count}/50 ({passed_count/50*100:.1f}%)", flush=True)
    print(f"Total Time: {total_time:.2f}s | Avg Latency: {total_time/50:.2f}s per query", flush=True)
    print("-" * 80, flush=True)

    summary_file = ROOT / "logs" / "verify_50_runs_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({"total": 50, "passed": passed_count, "results": results}, f, indent=2)

    print(f"Full report saved -> {summary_file}", flush=True)
    return results, passed_count


if __name__ == "__main__":
    run_50_query_verification()
