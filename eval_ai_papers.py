"""
eval_ai_papers.py
-----------------
Benchmark runner for the AI papers Q&A evaluation set.

Usage:
    python eval_ai_papers.py

Reads:  eval/ai_papers_expected_answers.json
Writes: logs/eval_results.jsonl  (one JSON line per question)
        logs/eval_summary.txt    (human-readable summary)

Environment:
    DISABLE_PROMPT_CACHE=1   (set automatically -- every run hits the LLM)
    REPO_ID=<uuid>           (optional: force all queries to a specific collection)
"""

import os
import sys
import json
import time
import gc
from pathlib import Path

# Force LLM cache disabled so we always get live inference
os.environ["DISABLE_PROMPT_CACHE"] = "1"

ROOT = Path(__file__).parent
EVAL_FILE = ROOT / "eval" / "ai_papers_expected_answers.json"
LOGS_DIR = ROOT / "logs"
RESULTS_FILE = LOGS_DIR / "eval_results.jsonl"
SUMMARY_FILE = LOGS_DIR / "eval_summary.txt"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

FORCED_REPO_ID = os.environ.get("REPO_ID", None)
AI_PAPERS_REPO_ID = "71e2cffe-8756-4ff3-b35c-52fc94babdd4"


def _check_answer(answer: str, key_concepts: list) -> dict:
    answer_lower = answer.lower()
    hits = []
    misses = []
    for concept in key_concepts:
        concept_words = concept.lower().split()
        if any(w in answer_lower for w in concept_words) or concept.lower() in answer_lower:
            hits.append(concept)
        else:
            misses.append(concept)
    hit_ratio = len(hits) / len(key_concepts) if key_concepts else 0.0
    cannot_find = "i cannot find this information in the uploaded documents"
    is_cannot_find = cannot_find in answer_lower
    passed = (hit_ratio >= 0.5) and (not is_cannot_find)
    return {
        "hits": hits,
        "misses": misses,
        "hit_ratio": round(hit_ratio, 3),
        "is_cannot_find": is_cannot_find,
        "passed": passed,
    }


def run_benchmark():
    try:
        from agents.orchestrator import answer as orchestrator_answer
    except Exception as e:
        print(f"[ERROR] Failed to import orchestrator: {e}", flush=True)
        sys.exit(1)

    if not EVAL_FILE.exists():
        print(f"[ERROR] Benchmark file not found: {EVAL_FILE}", flush=True)
        sys.exit(1)

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print("=" * 70, flush=True)
    print(f"AI PAPERS BENCHMARK  --  {len(questions)} questions", flush=True)
    print(f"Repo ID: {FORCED_REPO_ID or AI_PAPERS_REPO_ID}", flush=True)
    print(f"Results -> {RESULTS_FILE}", flush=True)
    print("=" * 70, flush=True)

    # Clear previous results for this run
    if RESULTS_FILE.exists():
        RESULTS_FILE.unlink()

    results = []
    passed_count = 0
    total_latency = 0.0

    for idx, q in enumerate(questions, 1):
        qid = q.get("id", f"Q{idx}")
        question = q["question"]
        expected = q.get("expected_answer", "")
        key_concepts = q.get("key_concepts", [])
        paper = q.get("paper", "")
        category = q.get("category", "general")

        repo_id = FORCED_REPO_ID or AI_PAPERS_REPO_ID

        print(f"\n{'=' * 70}", flush=True)
        print(f"[{idx}/{len(questions)}] {qid} | {category}", flush=True)
        print(f"Paper   : {paper}", flush=True)
        print(f"Question: {question}", flush=True)
        print(f"Expected concepts: {key_concepts}", flush=True)

        t0 = time.perf_counter()
        try:
            result = orchestrator_answer(
                query=question,
                repo_id=repo_id,
                filters={},
                retrieval_mode="single",
            )
            if isinstance(result, tuple):
                answer_text = result[0]
                latency_bd = result[1] if len(result) > 1 else {}
                chunks_returned = result[2] if len(result) > 2 else []
            else:
                answer_text = str(result)
                latency_bd = {}
                chunks_returned = []
        except Exception as e:
            answer_text = f"[EXCEPTION] {e}"
            latency_bd = {}
            chunks_returned = []

        elapsed = time.perf_counter() - t0
        total_latency += elapsed

        # Free memory between queries to prevent numpy allocation failures
        # when running 14+ LLM inferences sequentially in the same process.
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        check = _check_answer(answer_text, key_concepts)
        if check["passed"]:
            passed_count += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"Status   : {status}", flush=True)
        print(f"Latency  : {elapsed:.2f}s", flush=True)
        print(f"Hit ratio: {check['hit_ratio']*100:.0f}% ({len(check['hits'])}/{len(key_concepts)} concepts)", flush=True)
        if check["misses"]:
            print(f"Missing  : {check['misses']}", flush=True)
        if check["is_cannot_find"]:
            print("WARNING: Answer is CANNOT_FIND_RESPONSE", flush=True)
        print(f"Answer preview: {answer_text[:300]}", flush=True)

        record = {
            "id": qid,
            "paper": paper,
            "category": category,
            "question": question,
            "expected_answer": expected,
            "key_concepts": key_concepts,
            "actual_answer": answer_text,
            "hit_ratio": check["hit_ratio"],
            "hits": check["hits"],
            "misses": check["misses"],
            "is_cannot_find": check["is_cannot_find"],
            "passed": check["passed"],
            "latency_s": round(elapsed, 3),
            "chunks_returned": len(chunks_returned),
            "repo_id": repo_id,
        }
        results.append(record)

        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    total = len(questions)
    score = passed_count / total if total else 0.0

    print("\n" + "=" * 70, flush=True)
    print("BENCHMARK SUMMARY", flush=True)
    print("=" * 70, flush=True)
    print(f"Total     : {total}", flush=True)
    print(f"Passed    : {passed_count}", flush=True)
    print(f"Failed    : {total - passed_count}", flush=True)
    print(f"Score     : {score*100:.1f}%", flush=True)
    print(f"Total lat : {total_latency:.1f}s  Avg: {total_latency/total:.1f}s", flush=True)

    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1
    print("\nBy category:", flush=True)
    for cat, counts in sorted(categories.items()):
        cat_score = counts["passed"] / counts["total"]
        print(f"  {cat:<25} {counts['passed']}/{counts['total']}  ({cat_score*100:.0f}%)", flush=True)

    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\nFailed questions:", flush=True)
        for r in failed:
            print(f"  {r['id']} [{r['category']}]: {r['question'][:70]}", flush=True)
            print(f"    Missing : {r['misses']}", flush=True)
            print(f"    no_find : {r['is_cannot_find']}", flush=True)

    summary_lines = [
        "AI Papers Benchmark Results",
        f"Score: {passed_count}/{total} ({score*100:.1f}%)",
        f"Total latency: {total_latency:.1f}s",
        "",
    ]
    for r in results:
        st = "PASS" if r["passed"] else "FAIL"
        summary_lines.append(
            f"{r['id']:4s} [{st}] hit={r['hit_ratio']*100:.0f}%  {r['question'][:60]}"
        )
    SUMMARY_FILE.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"\nSummary -> {SUMMARY_FILE}", flush=True)

    return score


if __name__ == "__main__":
    score = run_benchmark()
    sys.exit(0 if score >= 0.5 else 1)
