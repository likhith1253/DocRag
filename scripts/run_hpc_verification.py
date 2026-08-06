"""
run_hpc_verification.py
------------------------
HPC-Optimized 50-Query Comprehensive Verification & Diagnostic Suite for DocumentRAG.

Saves ALL forensic details for all 50 queries into a SINGLE master file:
  - Markdown: logs/hpc_50_runs_comprehensive_report.md
  - JSON:     logs/hpc_50_runs_comprehensive_report.json

Usage:
  python scripts/run_hpc_verification.py
"""

import os
import sys
import time
import json
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Disable LLM prompt cache so every query hits live GPU generation
os.environ["ENABLE_PROMPT_CACHE"] = "0"
os.environ["DISABLE_PROMPT_CACHE"] = "1"

EVAL_FILE = ROOT / "eval" / "dataset" / "ai_papers.json"
LOGS_DIR = (ROOT / "logs").resolve()
LOGS_DIR.mkdir(parents=True, exist_ok=True)

REPORT_MD = LOGS_DIR / "hpc_50_runs_comprehensive_report.md"
REPORT_JSON = LOGS_DIR / "hpc_50_runs_comprehensive_report.json"

SYNONYM_MAP = {
    "parallelization": ["parallel execution", "parallel processing", "pipelining", "parallel computing", "parallelism"],
    "manual annotation": ["annotated manually", "manually annotated", "human annotation", "manual labeling", "annotated"],
    "latent factors": ["latent dimensions", "latent vectors", "latent features", "embedding dimension", "latent space"],
    "learning rate": ["lr", "learning_rate", "step size", "learning_rate="],
    "training distribution": ["train distribution", "data distribution", "training dataset", "sample distribution"],
    "feature space": ["feature representation", "vector space", "embedding space", "feature vector"],
    "agent-based modeling": ["agent based modeling", "agent modeling", "multi-agent simulation", "abm", "agent-based"],
    "simulation": ["simulated", "simulation model", "simulation environment", "simulator"],
    "joint positions": ["joint coordinates", "skeleton joints", "joint locations", "joint data"],
}


def evaluate_answer(answer, key_concepts):
    answer_lower = answer.lower()
    hits = []
    misses = []
    for concept in key_concepts:
        concept_lower = concept.lower()
        concept_words = concept_lower.split()
        synonyms = SYNONYM_MAP.get(concept_lower, [])

        matched = (
            concept_lower in answer_lower
            or any(syn in answer_lower for syn in synonyms)
            or (len(concept_words) > 1 and all(w in answer_lower for w in concept_words))
            or any(w in answer_lower for w in concept_words if len(w) > 4)
        )
        if matched:
            hits.append(concept)
        else:
            misses.append(concept)

    hit_ratio = len(hits) / len(key_concepts) if key_concepts else 0.0
    cannot_find = "i cannot find this information" in answer_lower
    passed = (hit_ratio >= 0.5) and (not cannot_find)
    return {
        "hits": hits,
        "misses": misses,
        "hit_ratio": round(hit_ratio, 3),
        "is_cannot_find": cannot_find,
        "passed": passed,
    }


def run_hpc_verification():
    from agents.orchestrator import answer as orchestrator_answer

    if not EVAL_FILE.exists():
        print(f"[ERROR] Benchmark file missing: {EVAL_FILE}", flush=True)
        sys.exit(1)

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Build 50 sequential query queue
    query_queue = []
    while len(query_queue) < 50:
        query_queue.extend(questions)
    query_queue = query_queue[:50]

    print("=" * 80, flush=True)
    print("DOCUMENTRAG HPC 50-QUERY COMPREHENSIVE VERIFICATION RUN", flush=True)
    print(f"Total Queries: {len(query_queue)}", flush=True)
    print(f"Master MD Report   -> {REPORT_MD}", flush=True)
    print(f"Master JSON Report -> {REPORT_JSON}", flush=True)
    print("=" * 80, flush=True)

    records = []
    passed_count = 0
    total_start = time.perf_counter()

    for idx, q_item in enumerate(query_queue, start=1):
        qid = q_item.get("id", f"Q{idx}")
        category = q_item.get("category", "general")
        target_paper = q_item.get("paper", "Unknown")
        question = q_item["question"]
        key_concepts = q_item.get("key_concepts", [])
        expected_answer = q_item.get("expected_answer", "")

        print(f"\n[{idx}/50] Running Query '{qid}' ({category}) ...", flush=True)
        print(f"  Target Paper : {target_paper}", flush=True)
        print(f"  Question     : {question}", flush=True)

        req_id = f"hpc_run_{idx}_{qid}"
        t0 = time.perf_counter()

        answer_text = ""
        latency_bd = {}
        chunks_retrieved = []
        citations_built = []
        err_msg = ""
        prompt_used = ""

        try:
            res = orchestrator_answer(
                query=question,
                repo_id=None,  # Searches active 'chunks' collection where all papers are indexed
                filters={},
                retrieval_mode="corpus",
                request_id=req_id,
            )
            if isinstance(res, tuple):
                answer_text = res[0]
                latency_bd = res[1] if len(res) > 1 else {}
                chunks_retrieved = res[2] if len(res) > 2 else []
                citations_built = res[3] if len(res) > 3 else []
            else:
                answer_text = str(res)

        except Exception as ex:
            err_msg = traceback.format_exc()
            answer_text = f"[EXCEPTION] {ex}"

        elapsed_sec = time.perf_counter() - t0

        # Read exact final prompt from logs/final_prompt.txt if created
        final_prompt_file = LOGS_DIR / "final_prompt.txt"
        if final_prompt_file.exists():
            try:
                prompt_used = final_prompt_file.read_text(encoding="utf-8")
            except Exception:
                prompt_used = "Unable to read final_prompt.txt"

        # Check answer quality
        eval_res = evaluate_answer(answer_text, key_concepts)
        status = "PASS" if eval_res["passed"] and not err_msg else ("CRASH" if err_msg else "FAIL")
        if status == "PASS":
            passed_count += 1

        chunk_summaries = []
        for c in chunks_retrieved:
            m = c.get("metadata", {})
            chunk_summaries.append({
                "chunk_id": str(c.get("id") or m.get("hash") or "unknown"),
                "score": float(c.get("score", 0.0)),
                "file": m.get("file") or m.get("paper_title") or "Unknown",
                "section": m.get("section", "Unknown"),
                "pages": f"{m.get('page_start', '?')}–{m.get('page_end', '?')}",
                "content_snippet": str(c.get("content", ""))[:250],
            })

        rec = {
            "run_index": idx,
            "qid": qid,
            "category": category,
            "target_paper": target_paper,
            "question": question,
            "expected_answer": expected_answer,
            "key_concepts": key_concepts,
            "status": status,
            "latency_total_sec": round(elapsed_sec, 2),
            "latency_breakdown_ms": latency_bd,
            "concept_eval": eval_res,
            "chunks_count": len(chunks_retrieved),
            "citations_count": len(citations_built),
            "chunks": chunk_summaries,
            "citations": citations_built,
            "generated_answer": answer_text,
            "prompt_text": prompt_used,
            "error_traceback": err_msg,
        }
        records.append(rec)

        print(
            f"  Status: {status} | Latency: {elapsed_sec:.2f}s (LLM: {latency_bd.get('llm_ms', 0):.0f}ms) | "
            f"Hits: {len(eval_res['hits'])}/{len(key_concepts)}",
            flush=True,
        )

    total_wall_sec = time.perf_counter() - total_start

    # -------------------------------------------------------------------
    # GENERATE MASTER MARKDOWN REPORT FILE
    # -------------------------------------------------------------------
    md = [
        "# DocumentRAG HPC 50-Query Comprehensive Master Verification Report",
        f"**Execution Date**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        f"**Total Queries Evaluated**: {len(records)}",
        f"**Overall Accuracy**: {passed_count}/{len(records)} ({passed_count/len(records)*100:.1f}%)",
        f"**Total Wall Time**: {total_wall_sec:.2f}s ({total_wall_sec/60:.2f} min)",
        f"**Average Query Latency**: {total_wall_sec/len(records):.2f}s",
        "",
        "---",
        "",
        "## 1. 50-Query Summary Matrix",
        "",
        "| Run # | QID | Category | Target Paper | Chunks | Citations | Hits / Concepts | Total Time (s) | LLM Time (ms) | Status |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]

    for r in records:
        ev = r["concept_eval"]
        hits_str = f"{len(ev['hits'])}/{len(r['key_concepts'])}"
        llm_ms = r['latency_breakdown_ms'].get('llm_ms', 0.0)
        paper_short = r['target_paper'][:25]
        md.append(
            f"| {r['run_index']} | {r['qid']} | {r['category']} | `{paper_short}` | {r['chunks_count']} | {r['citations_count']} | {hits_str} | {r['latency_total_sec']}s | {llm_ms:.0f}ms | **{r['status']}** |"
        )

    md.extend([
        "",
        "---",
        "",
        "## 2. Detailed Per-Query Forensic Records",
        "",
    ])

    for r in records:
        ev = r["concept_eval"]
        md.extend([
            f"### Run #{r['run_index']} — Question {r['qid']} ({r['category']})",
            f"- **Status**: **{r['status']}**",
            f"- **Target Paper**: `{r['target_paper']}`",
            f"- **Question**: {r['question']}",
            f"- **Key Concepts**: `{r['key_concepts']}`",
            f"- **Concept Hits**: `{ev['hits']}`",
            f"- **Concept Misses**: `{ev['misses']}`",
            f"- **Hit Ratio**: `{ev['hit_ratio']}`",
            f"- **Total Latency**: `{r['latency_total_sec']}s`",
            f"- **Latency Breakdown (ms)**: `{json.dumps(r['latency_breakdown_ms'])}`",
            f"- **Chunks Retrieved ({r['chunks_count']})**:",
        ])
        for ch in r["chunks"]:
            md.append(f"  - `[{ch['chunk_id']}]` (Score: {ch['score']:.4f}) | File: `{ch['file']}` | Section: `{ch['section']}` | Page: `{ch['pages']}`")

        md.extend([
            f"- **Citations Built ({r['citations_count']})**: `{json.dumps(r['citations'])}`",
            "",
            "#### Generated Answer",
            "```markdown",
            r["generated_answer"],
            "```",
            "",
            "#### Prompt Sent to LLM (Truncated Excerpt)",
            "```markdown",
            r["prompt_text"][:2000] + ("\n...[FULL PROMPT TRUNCATED IN REPORT MD - FULL PROMPT IN JSON]" if len(r["prompt_text"]) > 2000 else ""),
            "```",
            "",
        ])
        if r["error_traceback"]:
            md.extend([
                "#### Error Traceback",
                "```text",
                r["error_traceback"],
                "```",
                "",
            ])
        md.append("---")

    report_md_str = "\n".join(md)
    REPORT_MD.write_text(report_md_str, encoding="utf-8")

    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "total_queries": len(records),
            "passed_count": passed_count,
            "accuracy_percent": round(passed_count / len(records) * 100, 2),
            "total_wall_time_sec": round(total_wall_sec, 2),
            "records": records,
        }, f, indent=2)

    print("\n" + "=" * 80, flush=True)
    print("HPC 50-QUERY VERIFICATION RUN COMPLETE!", flush=True)
    print(f"Passed: {passed_count}/50 ({passed_count/len(records)*100:.1f}%)", flush=True)
    print(f"Master MD Report   -> {REPORT_MD}", flush=True)
    print(f"Master JSON Report -> {REPORT_JSON}", flush=True)
    print("=" * 80, flush=True)


if __name__ == "__main__":
    run_hpc_verification()
