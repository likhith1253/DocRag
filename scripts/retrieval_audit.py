"""
scripts/retrieval_audit.py
--------------------------
Forensic 6-Stage Retrieval Audit Tool for DocumentRAG.

Traces ground-truth evidence for all benchmark questions through the complete 6-stage lifecycle:
  1. Collection Index: Does the chunk containing key concepts exist in Qdrant?
  2. Vector Search (Top-100): Is it retrieved during dense vector search?
  3. MMR Reranking: Is it preserved after MMR diversity filtering?
  4. CrossEncoder (Top-8): Is it ranked in the top-8 by CrossEncoder?
  5. Prompt Assembly: Is it included in the context block sent to the LLM?
  6. LLM Answer: Did the generated answer incorporate the key concept?

Outputs a comprehensive diagnostic markdown report to:
  logs/retrieval_audit_report.md
  logs/retrieval_audit_report.json
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Force prompt cache off for live execution
os.environ["DISABLE_PROMPT_CACHE"] = "1"

EVAL_FILE = ROOT / "eval" / "dataset" / "ai_papers.json"
if not EVAL_FILE.exists():
    EVAL_FILE = ROOT / "eval" / "ai_papers_expected_answers.json"

LOGS_DIR = (ROOT / "logs").resolve()
LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPORT_MD = LOGS_DIR / "retrieval_audit_report.md"
REPORT_JSON = LOGS_DIR / "retrieval_audit_report.json"

AI_PAPERS_REPO_ID = "71e2cffe-8756-4ff3-b35c-52fc94babdd4"


def run_retrieval_audit():
    print("=" * 80, flush=True)
    print("DOCUMENTRAG 6-STAGE RETRIEVAL AUDIT", flush=True)
    print("=" * 80, flush=True)

    from storage.vector_store import VectorStoreManager
    from retrieval.mmr_rerank import mmr_rerank
    from retrieval.cross_encoder_rerank import rerank_cross_encoder
    from agents.doc_agent import _build_context_block
    from agents.orchestrator import answer as orchestrator_answer

    collection_name = f"collection_{AI_PAPERS_REPO_ID}"
    vsm = VectorStoreManager(collection_name=collection_name)
    all_chunks = vsm.get_all_chunks()
    print(f"[AUDIT] Total indexed chunks in collection: {len(all_chunks)}", flush=True)

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        benchmark_items = json.load(f)

    audit_results = []

    for idx, item in enumerate(benchmark_items, 1):
        qid = item.get("id", f"Q{idx}")
        question = item["question"]
        target_paper = item.get("paper", "")
        key_concepts = item.get("key_concepts", [])
        category = item.get("category", "general")

        print(f"\n[{idx}/{len(benchmark_items)}] Auditing {qid} ({category}) ...", flush=True)
        print(f"  Target Paper : {target_paper}", flush=True)
        print(f"  Key Concepts : {key_concepts}", flush=True)

        # -------------------------------------------------------------------
        # STAGE 1: Collection Indexing Check
        # Search all chunks for target paper + key concept matches
        # -------------------------------------------------------------------
        paper_chunks = [
            c for c in all_chunks
            if target_paper.lower() in (c.get("metadata", {}).get("file", "") or c.get("metadata", {}).get("paper_title", "")).lower()
               or (c.get("metadata", {}).get("file", "").lower() in target_paper.lower())
        ]

        concept_matched_chunks = []
        for c in paper_chunks:
            c_text = c.get("content", "").lower()
            matching_concepts = [kc for kc in key_concepts if kc.lower() in c_text]
            if matching_concepts:
                concept_matched_chunks.append({
                    "chunk_id": str(c.get("id") or c.get("metadata", {}).get("hash") or ""),
                    "section": c.get("metadata", {}).get("section", "Unknown"),
                    "page_start": c.get("metadata", {}).get("page_start", "?"),
                    "matched_concepts": matching_concepts,
                    "chunk": c,
                })

        stage1_exists = len(concept_matched_chunks) > 0
        matched_chunk_ids = set(cmc["chunk_id"] for cmc in concept_matched_chunks)

        # -------------------------------------------------------------------
        # STAGE 2: Vector Search (Top-100)
        # -------------------------------------------------------------------
        vec_top100, _ = vsm.search(query=question, top_k=100)
        stage2_top100_ids = [str(c.get("id") or c.get("metadata", {}).get("hash") or "") for c in vec_top100]
        
        stage2_hit_ranks = {}
        for rank, cid in enumerate(stage2_top100_ids, 1):
            if cid in matched_chunk_ids:
                stage2_hit_ranks[cid] = rank

        stage2_retrieved = len(stage2_hit_ranks) > 0

        # -------------------------------------------------------------------
        # STAGE 3: MMR Reranking (Top-20)
        # -------------------------------------------------------------------
        mmr_chunks = mmr_rerank(query=question, chunks=vec_top100, top_k=20, request_id=f"audit_{qid}")
        stage3_mmr_ids = [str(c.get("id") or c.get("metadata", {}).get("hash") or "") for c in mmr_chunks]

        stage3_hit_ranks = {}
        for rank, cid in enumerate(stage3_mmr_ids, 1):
            if cid in matched_chunk_ids:
                stage3_hit_ranks[cid] = rank

        stage3_retrieved = len(stage3_hit_ranks) > 0

        # -------------------------------------------------------------------
        # STAGE 4: CrossEncoder Reranking (Top-8)
        # -------------------------------------------------------------------
        ce_chunks = rerank_cross_encoder(query=question, chunks=mmr_chunks, top_k=8, request_id=f"audit_{qid}")
        stage4_ce_ids = [str(c.get("id") or c.get("metadata", {}).get("hash") or "") for c in ce_chunks]

        stage4_hit_ranks = {}
        for rank, cid in enumerate(stage4_ce_ids, 1):
            if cid in matched_chunk_ids:
                stage4_hit_ranks[cid] = rank

        stage4_retrieved = len(stage4_hit_ranks) > 0

        # -------------------------------------------------------------------
        # STAGE 5: Context Prompt Assembly
        # -------------------------------------------------------------------
        trace_lines = []
        context_block = _build_context_block(ce_chunks, trace_lines)
        stage5_assembled = len(context_block) > 0

        # -------------------------------------------------------------------
        # STAGE 6: Ground-Truth Target Paper Chunk Verification in Prompt
        # Verifies that exact target paper content & matching chunk exist in prompt
        # -------------------------------------------------------------------
        target_stem = target_paper.replace(".pdf", "").replace("_", " ").lower()[:20]
        stage6_gt_in_prompt = False
        for cmc in concept_matched_chunks:
            chunk_text = str(cmc["chunk"].get("content", "")).strip().lower()
            if len(chunk_text) > 30 and chunk_text[:50] in context_block.lower():
                stage6_gt_in_prompt = True
                break
            # Fallback check: concept in context block
            for kc in cmc["matched_concepts"]:
                if kc.lower() in context_block.lower():
                    stage6_gt_in_prompt = True
                    break

        # -------------------------------------------------------------------
        # STAGE 7: LLM Evidence Utilization & Extraction Audit
        # (Live LLM generation or load from latest eval_results.jsonl)
        # -------------------------------------------------------------------
        answer_text = ""
        eval_results_file = LOGS_DIR / "eval_results.jsonl"
        if eval_results_file.exists():
            with open(eval_results_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        if rec.get("id") == qid:
                            answer_text = rec.get("actual_answer", "")
                            break
                    except Exception:
                        pass

        if not answer_text:
            try:
                ans_res = orchestrator_answer(query=question, repo_id=AI_PAPERS_REPO_ID, filters={}, retrieval_mode="single")
                answer_text = ans_res[0] if isinstance(ans_res, tuple) else str(ans_res)
            except Exception as ex:
                answer_text = f"[ERROR] {ex}"

        answer_lower = answer_text.lower()
        ans_hits = []
        for kc in key_concepts:
            kc_lower = kc.lower()
            # Direct match or word match
            if kc_lower in answer_lower or any(w in answer_lower for w in kc_lower.split() if len(w) > 3):
                ans_hits.append(kc)

        cannot_find = "i cannot find this information" in answer_lower
        stage7_utilization_pass = (len(ans_hits) / len(key_concepts) >= 0.5) and (not cannot_find) if key_concepts else False

        # Identify exact failure stage
        if not stage1_exists:
            failure_stage = "Stage 1: Chunk missing from DB Collection"
        elif not stage2_retrieved:
            failure_stage = "Stage 2: Not in Top-100 Vector Search"
        elif not stage3_retrieved:
            failure_stage = "Stage 3: Pruned by MMR Reranking"
        elif not stage4_retrieved:
            failure_stage = "Stage 4: Pruned by CrossEncoder (Not in Top-8)"
        elif not stage5_assembled:
            failure_stage = "Stage 5: Failed Prompt Context Assembly"
        elif not stage6_gt_in_prompt:
            failure_stage = "Stage 6: Target Paper Evidence Missing from Prompt Context"
        elif not stage7_utilization_pass:
            failure_stage = "Stage 7: Evidence Omitted / Not Utilized by LLM"
        else:
            failure_stage = "NONE (ALL STAGES PASSED)"

        record = {
            "qid": qid,
            "category": category,
            "paper": target_paper,
            "question": question,
            "key_concepts": key_concepts,
            "stage1_in_db": stage1_exists,
            "stage1_matching_chunks_count": len(concept_matched_chunks),
            "stage2_top100_retrieved": stage2_retrieved,
            "stage2_top100_ranks": stage2_hit_ranks,
            "stage3_mmr_retrieved": stage3_retrieved,
            "stage3_mmr_ranks": stage3_hit_ranks,
            "stage4_ce_retrieved": stage4_retrieved,
            "stage4_ce_ranks": stage4_hit_ranks,
            "stage5_assembled": stage5_assembled,
            "stage6_gt_in_prompt": stage6_gt_in_prompt,
            "stage7_utilization_pass": stage7_utilization_pass,
            "stage7_concepts_hit": ans_hits,
            "failure_stage": failure_stage,
        }
        audit_results.append(record)

    # -------------------------------------------------------------------
    # GENERATE MARKDOWN AUDIT REPORT
    # -------------------------------------------------------------------
    md_lines = [
        "# DocumentRAG 7-Stage Retrieval & Evidence Utilization Audit Report",
        f"**Date**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        f"**Total Questions Audited**: {len(audit_results)}",
        "",
        "## Summary Matrix",
        "",
        "| QID | Category | Stage 1 (DB) | Stage 2 (V100) | Stage 3 (MMR20) | Stage 4 (CE8) | Stage 5 (Prompt) | Stage 6 (GT in Prompt) | Stage 7 (LLM Utilized) | Failure Point |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in audit_results:
        s1 = "YES" if r["stage1_in_db"] else "NO"
        s2 = f"YES (R{list(r['stage2_top100_ranks'].values())[0]})" if r["stage2_top100_ranks"] else ("YES" if r["stage2_top100_retrieved"] else "NO")
        s3 = f"YES (R{list(r['stage3_mmr_ranks'].values())[0]})" if r["stage3_mmr_ranks"] else ("YES" if r["stage3_mmr_retrieved"] else "NO")
        s4 = f"YES (R{list(r['stage4_ce_ranks'].values())[0]})" if r["stage4_ce_ranks"] else ("YES" if r["stage4_ce_retrieved"] else "NO")
        s5 = "YES" if r["stage5_assembled"] else "NO"
        s6 = "YES" if r["stage6_gt_in_prompt"] else "NO"
        s7 = "YES" if r["stage7_utilization_pass"] else "NO"
        md_lines.append(
            f"| {r['qid']} | {r['category']} | {s1} | {s2} | {s3} | {s4} | {s5} | {s6} | {s7} | **{r['failure_stage']}** |"
        )

    md_lines.extend([
        "",
        "## Detailed Per-Question Decomposition",
        "",
    ])

    for r in audit_results:
        md_lines.extend([
            f"### {r['qid']}: {r['question']}",
            f"- **Target Paper**: `{r['paper']}`",
            f"- **Key Concepts**: `{r['key_concepts']}`",
            f"- **Failure Stage**: `{r['failure_stage']}`",
            f"- **Stage 1 (In DB Collection)**: {r['stage1_in_db']} ({r['stage1_matching_chunks_count']} matching chunks found)",
            f"- **Stage 2 (Vector Top-100)**: {r['stage2_top100_retrieved']} (Hit Ranks: {r['stage2_top100_ranks']})",
            f"- **Stage 3 (MMR Top-20)**: {r['stage3_mmr_retrieved']} (Hit Ranks: {r['stage3_mmr_ranks']})",
            f"- **Stage 4 (CrossEncoder Top-8)**: {r['stage4_ce_retrieved']} (Hit Ranks: {r['stage4_ce_ranks']})",
            f"- **Stage 5 (Prompt Assembly)**: {r['stage5_assembled']}",
            f"- **Stage 6 (Target Paper GT Chunk in Prompt)**: {r['stage6_gt_in_prompt']}",
            f"- **Stage 7 (LLM Evidence Utilization)**: {r['stage7_utilization_pass']} (Concepts Hit: {r['stage7_concepts_hit']})",
            "",
        ])

    report_content = "\n".join(md_lines)
    REPORT_MD.write_text(report_content, encoding="utf-8")
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2)

    print(f"\n[AUDIT COMPLETE] Wrote {len(report_content)} chars -> {REPORT_MD}", flush=True)
    print(f"[AUDIT COMPLETE] Wrote {len(audit_results)} items -> {REPORT_JSON}", flush=True)
    return audit_results


if __name__ == "__main__":
    run_retrieval_audit()
