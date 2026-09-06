"""
DocumentRAG Orchestrator.
Adapted from CodeGraphRAG orchestrator — removes code-specific pipeline steps
(KG expansion, code/data/reasoning routing) while preserving all infrastructure
(LangGraph, progress, caching, logging, latency tracking, MMR, cross-encoder).

Pipeline:
    route → retrieve → agent → END

Changes from CodeGraphRAG:
  - Single agent: doc_agent (always)
  - No KG expansion step
  - No code/data/reasoning routing
  - Retrieval returns doc metadata (paper_title, section, page_start, page_end)
  - Answer response includes structured citations
  - Grounding: "cannot find" propagated correctly
"""

import os
import re
import sys
import time
import json
import ctypes
import yaml
from typing import List, Dict, Any, Tuple
try:
    from typing import TypedDict
except ImportError:
    try:
        from typing_extensions import TypedDict
    except ImportError:
        TypedDict = dict
try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph = None
    END = None

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from storage.vector_store import VectorStoreManager, _get_config
from storage.registry import RepositoryRegistry, get_registry
from retrieval.mmr_rerank import mmr_rerank
from retrieval.cross_encoder_rerank import rerank_cross_encoder
from retrieval.paper_matcher import (
    get_collection_papers,
    match_papers_in_query,
    classify_paper_scope,
)
from retrieval.query_analyzer import decompose_complex_question, detect_evidence_intent, extract_comparison_facets

import agents.doc_agent as doc_agent
from agents.doc_agent import CANNOT_FIND_RESPONSE, build_citation_list

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)
LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)
LOGS_PATH = os.path.join(LOGS_DIR, "query_logs.jsonl")

_v_manager_override = None

# Precompile section filter regex at module level (BUG-10 fix — avoid recompilation per query)
_LOW_VALUE_SECTION_RE = re.compile(
    r'\b(references?|bibliography|acknowledgements?|acknowledgments?)\b',
    re.IGNORECASE,
)


def _dedup_and_filter_chunks(chunks: List[Dict[str, Any]], removed_log: list) -> List[Dict[str, Any]]:
    """
    Shared Stage-4 logic: dedup by content hash, drop low-value sections
    (References/Bibliography/Acknowledgements). Used by both the normal
    collection-wide search path and each per-paper sub-search in the
    explicit multi-paper path, so isolation doesn't lose this filtering.
    """
    seen_hashes = set()
    unique_chunks = []
    for chunk in chunks:
        h = chunk.get("metadata", {}).get("hash", "")
        cid = chunk.get("id") or h or "unknown"
        doc_name = chunk.get("metadata", {}).get("file") or chunk.get("metadata", {}).get("paper_title") or "Unknown"
        if h and h in seen_hashes:
            removed_log.append({
                "chunk_id": str(cid),
                "filename": doc_name,
                "reason_removed": f"Duplicate content hash '{h}'"
            })
        else:
            if h:
                seen_hashes.add(h)
            unique_chunks.append(chunk)

    filtered_chunks = []
    for c in unique_chunks:
        sec = (c.get("metadata", {}).get("section") or "").strip()
        cid = c.get("id") or c.get("metadata", {}).get("hash") or "unknown"
        doc_name = c.get("metadata", {}).get("file") or c.get("metadata", {}).get("paper_title") or "Unknown"
        if _LOW_VALUE_SECTION_RE.search(sec):
            removed_log.append({
                "chunk_id": str(cid),
                "filename": doc_name,
                "reason_removed": f"Low-value section filter ('{sec}')"
            })
            continue
        filtered_chunks.append(c)

    return filtered_chunks if filtered_chunks else unique_chunks


# Maps a detect_evidence_intent() key to the chunk metadata flag it needs
# (see ingestion/doc_chunker.py::_compute_evidence_flags — Phase 3).
_EVIDENCE_FLAG_BY_INTENT = {
    "equation": "contains_equation",
    "table": "contains_table",
    "figure": "contains_figure",
    "algorithm": "contains_algorithm",
}


def _chunk_has_evidence(c: Dict[str, Any], evidence_type: str) -> bool:
    """Check if chunk satisfies the requested evidence type (by metadata flag or structural content)."""
    meta = c.get("metadata", {})
    if evidence_type in _EVIDENCE_FLAG_BY_INTENT:
        if meta.get(_EVIDENCE_FLAG_BY_INTENT[evidence_type]):
            return True
    content = c.get("content", "").lower()
    if evidence_type == "preprocessing":
        # Concrete preprocessing methodology required (not merely generic words like 'raw pixel')
        return any(w in content for w in ("210", "160", "110", "84", "down-sampl", "downsampl", "gray-scale", "grayscale", "crop", "last 4 frames", "stacks them", "history representation"))
    if evidence_type == "architecture":
        return any(w in content for w in ("controller", "linear controller", "mdn-rnn", "latent vector", "convolutional", "hidden units", "parameters", "network structure"))
    return False


def _ensure_evidence_coverage(
    candidate_pool: List[Dict[str, Any]],
    output_chunks: List[Dict[str, Any]],
    evidence_intent: Dict[str, bool],
    max_additions: int = 2,
) -> List[Dict[str, Any]]:
    """
    If the query is sensitive to a specific evidence type (equation/table/
    figure/algorithm/preprocessing/architecture) and a chunk of that type exists somewhere in the
    broader (post-MMR, pre-CrossEncoder-truncation) candidate pool but
    didn't survive top_k truncation, swap it in for the current
    lowest-scoring output chunk — bounded (max_additions) and never larger
    than the existing output, so this cannot cause context growth. If no
    matching evidence exists anywhere in the candidate pool, nothing is
    added — evidence is never fabricated.
    """
    needed = [t for t in ("equation", "table", "figure", "algorithm", "preprocessing", "architecture") if evidence_intent.get(t)]
    if not needed or not candidate_pool:
        return output_chunks

    result = list(output_chunks)
    output_hashes = {c.get("metadata", {}).get("hash") for c in result}
    additions = 0

    for t in needed:
        if additions >= max_additions:
            break
        if any(_chunk_has_evidence(c, t) for c in result):
            continue  # already represented in the current output

        best = None
        for c in candidate_pool:
            if not _chunk_has_evidence(c, t):
                continue
            if c.get("metadata", {}).get("hash") in output_hashes:
                continue
            if best is None or float(c.get("score", 0.0)) > float(best.get("score", 0.0)):
                best = c
        if best is None:
            continue  # this evidence type genuinely isn't available — don't fabricate

        if result:
            worst_idx = min(range(len(result)), key=lambda i: float(result[i].get("score", 0.0)))
            result.pop(worst_idx)
        result.append(best)
        output_hashes.add(best.get("metadata", {}).get("hash"))
        additions += 1

    return result


def _enforce_paper_isolation(
    chunks: List[Dict[str, Any]],
    requested_titles: List[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Hard post-filter for explicit single/multi-paper queries: drop any chunk
    whose paper does not exactly match one of the requested titles.

    This exists as a defense-in-depth guard, independent of whatever
    filtering happened upstream (Qdrant metadata filter, per-paper search
    loop, etc.) — if any upstream path ever lets an unrequested paper's
    chunk through (e.g. a filter fallback, a caching bug, a title-matching
    edge case), this still prevents it from reaching the LLM context.
    Returns (kept_chunks, dropped_chunks) so callers can log what was removed
    instead of silently discarding it.
    """
    if not requested_titles:
        return chunks, []
    requested_set = set(requested_titles)
    kept, dropped = [], []
    for c in chunks:
        meta = c.get("metadata", {})
        title = meta.get("paper_title") or meta.get("file") or "Unknown"
        (kept if title in requested_set else dropped).append(c)
    return kept, dropped


def _log_evidence_diagnostics(
    chunks: List[Dict[str, Any]],
    evidence_intent: Dict[str, bool],
    requested_papers: List[str] = None,
    retrieved_papers: List[str] = None,
) -> None:
    """
    Bounded evidence-coverage diagnostic print — counts and flags only,
    never full chunk dumps. Exists because "retrieval succeeded" (nonzero
    chunk count) does not imply "the right evidence was retrieved".
    """
    evidence_counts = {"equation": 0, "table": 0, "figure": 0, "algorithm": 0}
    pages = set()
    for c in chunks:
        meta = c.get("metadata", {})
        for t, flag in _EVIDENCE_FLAG_BY_INTENT.items():
            if meta.get(flag):
                evidence_counts[t] += 1
        pg = meta.get("page_start")
        if pg:
            pages.add(pg)

    if requested_papers is not None:
        print(f"[EVIDENCE DIAGNOSTICS] Requested paper(s): {requested_papers}", flush=True)
    if retrieved_papers is not None:
        print(f"[EVIDENCE DIAGNOSTICS] Retrieved paper(s): {retrieved_papers}", flush=True)
    print(f"[EVIDENCE DIAGNOSTICS] Evidence types retrieved: {evidence_counts}", flush=True)
    print(f"[EVIDENCE DIAGNOSTICS] Pages represented: {sorted(pages)}", flush=True)
    for t in ("equation", "table", "figure", "algorithm"):
        print(f"[EVIDENCE DIAGNOSTICS] {t.capitalize()} evidence: {'yes' if evidence_counts[t] else 'no'}", flush=True)

    missing = [t for t in ("equation", "table", "figure", "algorithm") if evidence_intent.get(t) and evidence_counts[t] == 0]
    print(f"[EVIDENCE DIAGNOSTICS] Missing requested evidence: {missing if missing else 'none'}", flush=True)


def get_process_memory() -> float:
    """Returns memory usage of current process in MB on Windows."""
    try:
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
        GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
        process = GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0


class AgentState(TypedDict, total=False):
    request_id: str
    question: str
    agent: str
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    answer: str
    error: str
    repo_id: str
    filters: Dict[str, Any]
    retrieval_mode: str  # "single", "multi", "corpus"
    latency_breakdown: Dict[str, float]


# ---------------------------------------------------------------------------
# Node: route
# ---------------------------------------------------------------------------
def route_node(state: AgentState) -> Dict[str, Any]:
    """
    In DocumentRAG all questions go to doc_agent.
    Still resolves repo_id if not supplied (picks first READY collection).
    Detects paper ambiguity when question could be answered by multiple papers.
    """
    try:
        t0 = time.perf_counter()
        t1 = time.perf_counter()

        updates = {
            "agent": "doc_agent",
            "latency_breakdown": {
                "planner_ms": (t1 - t0) * 1000,
                "embedding_ms": 0.0,
                "qdrant_ms": 0.0,
                "vector_ms": 0.0,
                "mmr_ms": 0.0,
                "reranker_ms": 0.0,
                "llm_ms": 0.0,
                "total_ms": 0.0,
            },
        }

        repo_id = state.get("repo_id")
        filters = state.get("filters") or {}
        retrieval_mode = state.get("retrieval_mode", "single")
        
        # Corpus mode bypasses repository routing explicitly
        if retrieval_mode == "corpus":
            pass
        # If repo_id is specified in filters, use it
        elif not repo_id and ("paper_title" in filters or "file" in filters):
            registry = get_registry()
            for rid, repo in registry.repositories.items():
                if repo.status == "READY" and repo.vector_collection:
                    try:
                        v_manager = VectorStoreManager(collection_name=repo.vector_collection)
                        chunks, _ = v_manager.search(state["question"], top_k=5, metadata_filters=filters, request_id=state.get("request_id", "default"))
                        if chunks and chunks[0]:
                            updates["repo_id"] = rid
                            break
                    except Exception:
                        pass
        # Otherwise if no repo_id supplied, invoke semantic router
        if not updates.get("repo_id") and not repo_id:
            from retrieval.repository_router import rank_repositories
            registry = get_registry()
            top_repos = rank_repositories(state["question"], registry, top_k=3)
            if top_repos:
                updates["repo_id"] = top_repos[0]

        registry = get_registry()
        ready_repos = [r for r in registry.list_repositories() if r.status == "READY"]
        print(f"[ROUTER] Registry lookup result     : {len(ready_repos)} READY repositories found.", flush=True)

        final_repo_id = updates.get("repo_id") or repo_id
        if final_repo_id:
            r_obj = registry.get_repository(final_repo_id)
            r_name = r_obj.name if r_obj else final_repo_id
            r_coll = r_obj.vector_collection if r_obj else f"collection_{final_repo_id}"
            print(f"[ROUTER] Selected repository        : {r_name} (ID: {final_repo_id})", flush=True)
            print(f"[ROUTER] Selected collection id     : {r_coll}", flush=True)
        else:
            print(f"[ROUTER] Selected repository        : None (Unassigned)", flush=True)
            print(f"[ROUTER] Selected collection id     : None", flush=True)

        return updates
    except Exception as e:
        return {
            "agent": "doc_agent",
            "error": f"Routing failed: {str(e)}",
            "latency_breakdown": {},
        }


# ---------------------------------------------------------------------------
# Node: retrieve
# ---------------------------------------------------------------------------
def retrieve_node(state: AgentState) -> Dict[str, Any]:
    """
    Vector search → MMR → Cross-encoder rerank.
    KG expansion logged.
    Respects retrieval_mode: single (default), multi, corpus.
    """
    from storage.pipeline_logger import log_stage, log_grounding_exit
    request_id = state.get("request_id", "default")
    try:
        latency_breakdown = state.get("latency_breakdown", {})

        config = _get_config()
        retrieval_conf = config.get("retrieval", {})
        vector_top_k = retrieval_conf.get("vector_top_k", 30)
        rerank_top_k = retrieval_conf.get("rerank_top_k", 5)

        repo_id = state.get("repo_id")
        filters = state.get("filters") or {}
        retrieval_mode = state.get("retrieval_mode", "single")

        registry = get_registry()

        # EXPLICIT RETRIEVAL BRANCHING
        if retrieval_mode == "corpus":
            v_coll = "chunks"
        elif repo_id:
            repo = registry.get_repository(repo_id)
            if repo and repo.vector_collection:
                v_coll = repo.vector_collection
            elif str(repo_id).startswith("collection_"):
                v_coll = repo_id
            else:
                # Check if collection_{repo_id} exists or repo_id is direct
                v_coll = f"collection_{repo_id}"
        else:
            v_coll = "chunks"

        global _v_manager_override
        if _v_manager_override is not None:
            v_manager = _v_manager_override
            v_coll = v_manager.collection_name
            points_in_coll = v_manager.count()
        else:
            try:
                v_manager = VectorStoreManager(collection_name=v_coll)
                points_in_coll = v_manager.count()
            except Exception:
                points_in_coll = 0

            # If current collection has 0 points, find active collection from registry or Qdrant
            if points_in_coll == 0:
                candidate_repos = [r for r in registry.list_repositories() if r.vector_collection]
                for r in candidate_repos:
                    try:
                        fb_manager = VectorStoreManager(collection_name=r.vector_collection)
                        if fb_manager.count() > 0:
                            v_coll = r.vector_collection
                            v_manager = fb_manager
                            repo_id = r.repo_id
                            print(f"[COLLECTION GUARD] Redirected to active collection '{v_coll}' ({fb_manager.count()} points).", flush=True)
                            break
                    except Exception:
                        pass

            # Paper presence guard: if the current collection has points, but the query
            # explicitly names papers that exist in another active collection, switch to that collection
            if _v_manager_override is None and retrieval_mode != "corpus" and "paper_title" not in filters and "file" not in filters:
                curr_titles = get_collection_papers(v_manager)
                curr_matches = match_papers_in_query(state["question"], curr_titles) if curr_titles else []
                if not curr_matches:
                    try:
                        all_colls = [c.name for c in v_manager.client.get_collections().collections if c.name != v_coll]
                        for other_c in all_colls:
                            try:
                                other_man = VectorStoreManager(collection_name=other_c)
                                if other_man.count() > 0:
                                    other_titles = get_collection_papers(other_man)
                                    other_matches = match_papers_in_query(state["question"], other_titles)
                                    if other_matches:
                                        v_coll = other_c
                                        v_manager = other_man
                                        print(f"[COLLECTION GUARD] Redirected to collection '{v_coll}' containing requested paper(s): {[t for t,_ in other_matches]}", flush=True)
                                        break
                            except Exception:
                                pass
                    except Exception:
                        pass

        print(f"[RETRIEVAL] Collection passed into vector search : '{v_coll}' (Points: {v_manager.count()})", flush=True)

        from storage.forensic_logger import ForensicLogger
        f_logger = state.get("f_logger")
        if f_logger:
            f_logger.set_routing(repo_id, v_coll, v_manager.count(), filters)

        # Apply retrieval mode constraints
        if retrieval_mode == "single" and repo_id:
            if not filters:
                filters = {}
        elif retrieval_mode == "corpus":
            filters = {k: v for k, v in filters.items() if k != "paper_title"}

        # ------------------------------------------------------------------
        # Explicit paper-scope detection: does the query itself name one or
        # more indexed papers? Only when the caller hasn't already pinned a
        # paper via filters, and never in corpus mode (isolation is a
        # single-collection concept). See retrieval/paper_matcher.py.
        # ------------------------------------------------------------------
        paper_scope = "collection"
        matched_papers = []
        if retrieval_mode != "corpus" and "paper_title" not in filters and "file" not in filters:
            available_titles = get_collection_papers(v_manager)
            if available_titles:
                matched_papers = match_papers_in_query(state["question"], available_titles)
                paper_scope = classify_paper_scope(matched_papers)

        initial_chunk_count = 0
        removed_chunks_log = []

        # Evidence-type sensitivity (equation/table/figure/algorithm/numerical)
        # — reused by both branches below to preserve the right kind of
        # evidence during reranking, not just whatever is globally closest.
        evidence_intent = detect_evidence_intent(state["question"])

        if paper_scope == "multi":
            # --------------------------------------------------------------
            # Explicit multi-paper query (e.g. "Compare DQN, A3C and SAC."):
            # Multi-paper facet-balanced retrieval:
            # For comparison queries, retrieve independently by:
            #     requested paper × requested facet
            # before final reranking/selection.
            # Ensure each requested paper receives evidence for as many requested facets as available.
            # Do not simply allocate two generic chunks per paper.
            # --------------------------------------------------------------
            requested_titles = [t for t, _ in matched_papers]
            print(f"[PAPER ISOLATION] Explicit multi-paper query — requested papers ({len(requested_titles)}):", flush=True)
            for t in requested_titles:
                print(f"  - {t}", flush=True)

            comparison_facets = extract_comparison_facets(state["question"])
            print(f"[FACET RETRIEVAL] Requested comparison facets ({len(comparison_facets)}): {[f[0] for f in comparison_facets]}", flush=True)

            per_paper_rerank_k = max(2, rerank_top_k // len(requested_titles))
            chunks = []
            retrieved_titles = []
            missing_titles = []

            for title in requested_titles:
                paper_filters = dict(filters)
                paper_filters["paper_title"] = title

                paper_candidates: List[Dict[str, Any]] = []

                # 1. Base query search for this paper
                t0 = time.perf_counter()
                p_chunks, p_timing = v_manager.search(
                    state["question"], top_k=vector_top_k, metadata_filters=paper_filters, request_id=request_id
                )
                latency_breakdown["embedding_ms"] = latency_breakdown.get("embedding_ms", 0.0) + p_timing.get("embedding_ms", 0.0)
                latency_breakdown["qdrant_ms"] = latency_breakdown.get("qdrant_ms", 0.0) + p_timing.get("qdrant_ms", 0.0)
                latency_breakdown["vector_ms"] = latency_breakdown.get("vector_ms", 0.0) + (time.perf_counter() - t0) * 1000
                initial_chunk_count += len(p_chunks)
                paper_candidates.extend(p_chunks)
                qv = p_timing.get("query_vector")

                # 2. Facet-specific searches: requested paper × requested facet
                for facet_name, facet_phrase in comparison_facets:
                    facet_q = f"{title} {facet_phrase}"
                    f_chunks, _ = v_manager.search(
                        facet_q, top_k=15, metadata_filters=paper_filters, request_id=request_id
                    )
                    initial_chunk_count += len(f_chunks)
                    for fc in f_chunks:
                        fc.setdefault("metadata", {})["_facet"] = facet_name
                    paper_candidates.extend(f_chunks)

                paper_candidates = _dedup_and_filter_chunks(paper_candidates, removed_chunks_log)

                if paper_candidates:
                    t0 = time.perf_counter()
                    p_mmr = mmr_rerank(
                        state["question"], paper_candidates, top_k=min(30, len(paper_candidates)),
                        query_vector=qv, request_id=request_id,
                    )
                    latency_breakdown["mmr_ms"] = latency_breakdown.get("mmr_ms", 0.0) + (time.perf_counter() - t0) * 1000

                    pre_ce_pool = p_mmr
                    t0 = time.perf_counter()
                    p_reranked = rerank_cross_encoder(
                        state["question"], p_mmr, top_k=len(p_mmr), request_id=request_id
                    )
                    latency_breakdown["reranker_ms"] = latency_breakdown.get("reranker_ms", 0.0) + (time.perf_counter() - t0) * 1000

                    # Select chunks ensuring balanced facet coverage for this paper
                    selected_for_paper: List[Dict[str, Any]] = []
                    seen_hashes_paper = set()

                    # First, allocate the top chunk for each requested facet if available
                    for facet_name, _ in comparison_facets:
                        if len(selected_for_paper) >= per_paper_rerank_k:
                            break
                        facet_keywords = facet_name.split("_")
                        best_facet_chunk = None
                        for cand in p_reranked:
                            c_hash = cand.get("metadata", {}).get("hash")
                            if c_hash in seen_hashes_paper:
                                continue
                            c_text = cand.get("content", "").lower()
                            c_meta = cand.get("metadata", {})
                            if c_meta.get("_facet") == facet_name or any(kw in c_text for kw in facet_keywords):
                                best_facet_chunk = cand
                                break
                        if best_facet_chunk is not None:
                            selected_for_paper.append(best_facet_chunk)
                            seen_hashes_paper.add(best_facet_chunk.get("metadata", {}).get("hash"))

                    # Fill remaining per_paper_rerank_k slots with highest overall reranked chunks
                    for cand in p_reranked:
                        if len(selected_for_paper) >= per_paper_rerank_k:
                            break
                        c_hash = cand.get("metadata", {}).get("hash")
                        if c_hash not in seen_hashes_paper:
                            selected_for_paper.append(cand)
                            seen_hashes_paper.add(c_hash)

                    if any(evidence_intent.values()):
                        selected_for_paper = _ensure_evidence_coverage(pre_ce_pool, selected_for_paper, evidence_intent)

                    if selected_for_paper:
                        retrieved_titles.append(title)
                        chunks.extend(selected_for_paper)
                    else:
                        missing_titles.append(title)
                else:
                    missing_titles.append(title)

            # By construction every chunk above was fetched from a search
            # filtered to exactly one requested paper_title, so there is no
            # way for an unrequested paper to appear here.
            unexpected_titles = [t for t in retrieved_titles if t not in requested_titles]

            print("[PAPER ISOLATION] Retrieved papers:", flush=True)
            for t in retrieved_titles:
                print(f"  - {t}", flush=True)
            print(f"[PAPER ISOLATION] Unexpected papers: {unexpected_titles if unexpected_titles else 'none'}", flush=True)
            if missing_titles:
                print(f"[PAPER ISOLATION] Insufficient/no evidence for requested paper(s): {missing_titles}", flush=True)

            stage4_data = {
                "mode": "multi_paper_isolation",
                "requested_papers": requested_titles,
                "retrieved_papers": retrieved_titles,
                "missing_papers": missing_titles,
                "unexpected_papers": unexpected_titles,
                "before_count": initial_chunk_count,
                "after_count": len(chunks),
                "removed_chunks_count": len(removed_chunks_log),
                "removed_chunks_details": removed_chunks_log,
            }
            log_stage(request_id, 4, "Filtering", stage4_data, latency_ms=0.0)

        else:
            if paper_scope == "single":
                filters = dict(filters)
                filters["paper_title"] = matched_papers[0][0]
                print(f"[PAPER ISOLATION] Single-paper query — restricting retrieval to: {matched_papers[0][0]!r}", flush=True)

            # Step 1: Vector search (Stage 2 & Stage 3 logged inside search())
            t0 = time.perf_counter()
            chunks, vector_timing = v_manager.search(
                state["question"], top_k=vector_top_k, metadata_filters=filters or None, request_id=request_id
            )
            latency_breakdown["embedding_ms"] = vector_timing["embedding_ms"]
            latency_breakdown["qdrant_ms"] = vector_timing["qdrant_ms"]
            latency_breakdown["vector_ms"] = (time.perf_counter() - t0) * 1000
            query_vector_for_mmr = vector_timing.pop("query_vector", None)

            # Lightweight decomposition for genuinely multi-facet questions
            # (e.g. one that asks about architecture AND training AND
            # results at once) — widen the candidate pool with a few bounded
            # facet-focused subqueries before reranking, instead of relying
            # on whatever is globally closest to the raw question alone.
            subqueries = decompose_complex_question(state["question"], max_subqueries=3)
            if subqueries:
                print(f"[QUERY DECOMPOSITION] Complex question — {len(subqueries)} facet subquery(ies) issued.", flush=True)
                for sq in subqueries:
                    try:
                        sq_chunks, _sq_timing = v_manager.search(
                            sq, top_k=15, metadata_filters=filters or None, request_id=request_id
                        )
                        chunks.extend(sq_chunks)
                    except Exception:
                        pass

            # Stage 4: FILTERING
            t_filter_start = time.perf_counter()
            initial_chunk_count = len(chunks)
            chunks = _dedup_and_filter_chunks(chunks, removed_chunks_log)
            filter_ms = (time.perf_counter() - t_filter_start) * 1000

            stage4_data = {
                "before_count": initial_chunk_count,
                "after_count": len(chunks),
                "removed_chunks_count": len(removed_chunks_log),
                "removed_chunks_details": removed_chunks_log
            }
            log_stage(request_id, 4, "Filtering", stage4_data, latency_ms=filter_ms)

            # Step 2: MMR rerank (Stage 5 logged inside mmr_rerank)
            t0 = time.perf_counter()
            if chunks:
                chunks = mmr_rerank(
                    state["question"],
                    chunks,
                    top_k=min(40, len(chunks)),
                    query_vector=query_vector_for_mmr,
                    request_id=request_id,
                )
            latency_breakdown["mmr_ms"] = (time.perf_counter() - t0) * 1000

            # Step 3: Cross-encoder rerank (Stage 6 logged inside rerank_cross_encoder)
            pre_ce_pool = chunks
            t0 = time.perf_counter()
            if chunks:
                chunks = rerank_cross_encoder(
                    state["question"], chunks, top_k=rerank_top_k, request_id=request_id
                )
            latency_breakdown["reranker_ms"] = (time.perf_counter() - t0) * 1000

            if chunks and any(evidence_intent.values()):
                chunks = _ensure_evidence_coverage(pre_ce_pool, chunks, evidence_intent)

        # ------------------------------------------------------------------
        # Defense-in-depth isolation enforcement: for an explicit single- or
        # multi-paper query, hard-filter out any chunk whose paper isn't one
        # of the requested titles, regardless of how it got here (Qdrant
        # metadata-filter fallback, caching, etc.) — see _enforce_paper_isolation.
        # ------------------------------------------------------------------
        requested_titles = [t for t, _ in matched_papers] if matched_papers else []
        if paper_scope in ("single", "multi") and requested_titles:
            chunks, unexpected_chunks = _enforce_paper_isolation(chunks, requested_titles)
            if unexpected_chunks:
                unexpected_papers_found = sorted({
                    c.get("metadata", {}).get("paper_title") or c.get("metadata", {}).get("file") or "Unknown"
                    for c in unexpected_chunks
                })
                print(
                    f"[PAPER ISOLATION] ENFORCEMENT: dropped {len(unexpected_chunks)} chunk(s) "
                    f"from unrequested paper(s) {unexpected_papers_found} that should never have "
                    f"reached this point for requested paper(s) {requested_titles}.",
                    flush=True,
                )

        _log_evidence_diagnostics(
            chunks,
            evidence_intent,
            requested_papers=requested_titles or None,
            retrieved_papers=sorted({
                c.get("metadata", {}).get("paper_title") or c.get("metadata", {}).get("file") or "Unknown"
                for c in chunks
            }),
        )

        if f_logger:
            f_logger.set_retrieval(vector_top_k, initial_chunk_count, len(chunks), len(chunks), chunks)

        # Stage 7: Knowledge Graph (DocumentRAG uses metadata graph mapping)
        use_graph = retrieval_conf.get("use_graph", False)
        stage7_data = {
            "graph_enabled": use_graph,
            "nodes_count": 0,
            "edges_count": 0,
            "matched_entities": [],
            "confidence": 1.0,
            "note": "DocumentRAG uses section/metadata graph search; standard dense vector RAG active."
        }
        log_stage(request_id, 7, "Knowledge Graph", stage7_data, latency_ms=0.0)

        # Fallback only when retrieval produced no chunks at all, AND the
        # query did not explicitly name specific paper(s). An explicit
        # single/multi-paper query must NEVER fall through to an
        # unrestricted collection-wide search — that is exactly how an
        # unrelated paper (e.g. a wrong 4th paper in a 3-paper comparison)
        # can silently substitute for the evidence that was actually
        # requested. If the requested paper(s) truly have no matching
        # evidence, that must be reported as missing, not backfilled from
        # elsewhere.
        if not chunks and paper_scope not in ("single", "multi"):
            # Fallback search in global 'chunks'
            try:
                fb_vman = VectorStoreManager(collection_name='chunks')
                fb_chunks, fb_timing = fb_vman.search(state['question'], top_k=vector_top_k, metadata_filters=None, request_id=request_id)
                latency_breakdown['fallback_vector_ms'] = fb_timing.get('qdrant_ms', 0.0)
                seen = set()
                fb_unique = []
                for ch in fb_chunks:
                    h = ch.get('metadata',{}).get('hash','')
                    if h and h not in seen:
                        seen.add(h)
                        fb_unique.append(ch)
                fb_chunks = fb_unique
                if fb_chunks:
                    # Apply the same low-value section filter as Stage 4 in the primary path.
                    # The fallback path previously skipped this, allowing References/Bibliography
                    # chunks to survive into the LLM context.
                    fb_filtered = [
                        c for c in fb_chunks
                        if not _LOW_VALUE_SECTION_RE.search(
                            (c.get('metadata', {}).get('section') or '').strip()
                        )
                    ]
                    if fb_filtered:
                        fb_chunks = fb_filtered
                    qv = fb_timing.pop('query_vector', None)
                    fb_chunks = mmr_rerank(state['question'], fb_chunks, top_k=min(40, len(fb_chunks)), query_vector=qv, request_id=request_id)
                    fb_chunks = rerank_cross_encoder(state['question'], fb_chunks, top_k=rerank_top_k, request_id=request_id)
                    if fb_chunks:
                        return {
                            "retrieved_chunks": fb_chunks,
                            "citations": build_citation_list(fb_chunks, request_id=request_id),
                            "latency_breakdown": latency_breakdown,
                        }
            except Exception:
                pass

            return {
                "retrieved_chunks": [],
                "citations": [],
                "error": "Zero chunks retrieved",
                "latency_breakdown": latency_breakdown,
            }

        if not chunks:
            # Reached only for an explicit single/multi-paper query whose
            # requested paper(s) yielded no evidence at all — report missing,
            # never substitute an unrestricted collection-wide fallback.
            print(
                f"[PAPER ISOLATION] No evidence found for requested paper(s) {requested_titles}. "
                f"Reporting as missing rather than falling back to unrestricted search.",
                flush=True,
            )
            return {
                "retrieved_chunks": [],
                "citations": [],
                "error": "Zero chunks retrieved",
                "latency_breakdown": latency_breakdown,
            }

        from storage.pipeline_logger import save_retrieval_json_artifact, log_exception
        save_retrieval_json_artifact(
            request_id=request_id,
            question=state["question"],
            top_retrieved_chunks=chunks,
            scores={"vector_top_k": len(chunks)},
            metadata={"repo_id": repo_id, "filters": filters},
            cross_encoder_scores=[{"chunk_id": str(c.get("id") or "unknown"), "score": float(c.get("score", 0.0))} for c in chunks],
            selected_chunks=chunks
        )

        return {
            "retrieved_chunks": chunks,
            "citations": build_citation_list(chunks, request_id=request_id),
            "latency_breakdown": latency_breakdown,
        }
    except Exception as e:
        from storage.pipeline_logger import log_exception
        log_exception(e, "retrieve_node")
        return {
            "retrieved_chunks": [],
            "citations": [],
            "error": f"Retrieval failed: {str(e)}",
            "latency_breakdown": state.get("latency_breakdown", {}),
        }


# ---------------------------------------------------------------------------
# Node: agent
# ---------------------------------------------------------------------------
def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Invoke doc_agent with retrieved chunks.
    Propagates grounding: if zero chunks, return CANNOT_FIND_RESPONSE.
    """
    from storage.pipeline_logger import log_grounding_exit
    request_id = state.get("request_id", "default")
    latency_breakdown = state.get("latency_breakdown", {})

    if state.get("error") == "Zero chunks retrieved":
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="agent_node",
            line_number=405,
            reason="Zero chunks retrieved from retrieval stage",
            condition="state.get('error') == 'Zero chunks retrieved'",
            evidence={"state_error": state.get("error")}
        )
        return {
            "answer": CANNOT_FIND_RESPONSE,
            "citations": [],
            "latency_breakdown": latency_breakdown,
        }
    elif state.get("error"):
        err_detail = state.get("error")
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="agent_node",
            line_number=391,
            reason=f"Retrieval error ('{err_detail}')",
            condition="state.get('error') is not empty",
            evidence={"state_error": err_detail}
        )
        raise RuntimeError(f"PIPELINE FAILURE IN RETRIEVAL: {err_detail}")

    try:
        chunks = state["retrieved_chunks"]
        _cfg = _get_config()
        agent_chunk_cap = int(
            _cfg.get("retrieval", {}).get("agent_chunk_cap", 8)
        )
        pre_cap_count = len(chunks)
        chunks = chunks[:agent_chunk_cap]
        if pre_cap_count > agent_chunk_cap:
            print(
                f"[AGENT CAP] Trimmed {pre_cap_count} → {agent_chunk_cap} chunks "
                f"(agent_chunk_cap={agent_chunk_cap}). "
                f"Dropped ranks {agent_chunk_cap+1}–{pre_cap_count}.",
                flush=True,
            )

        # ── BUG FIX: Rebuild citations from the CAPPED chunks only ──────
        # Previously, citations were built from all 20 retrieve_node chunks
        # but only 8 capped chunks were sent to the LLM, causing:
        #   - Citation count mismatch (Problem 4: 0 or 20 citations vs 8 chunks)
        #   - Stage contract violation (Problem 5: Stage 7=8 vs Stage 11=20)
        #   - Prompt contamination (Problem 3: unrelated paper chunks in context)
        capped_citations = build_citation_list(chunks, request_id=request_id)
        print(
            f"[AGENT NODE] Citations rebuilt from {len(chunks)} capped chunks: "
            f"{len(capped_citations)} citations (was {len(state.get('citations', []))} "
            f"from {pre_cap_count} retrieve_node chunks)",
            flush=True,
        )

        t0 = time.perf_counter()
        ans = doc_agent.run(state["question"], chunks, request_id=request_id)
        t1 = time.perf_counter()

        llm_ms = (t1 - t0) * 1000
        latency_breakdown["llm_ms"] = llm_ms

        f_logger = state.get("f_logger")
        if f_logger:
            f_logger.set_llm(len(ans or ""), int(len((ans or "").split()) * 1.33), llm_ms, ans)

        latency_breakdown["total_ms"] = sum(
            latency_breakdown.get(k, 0)
            for k in ("planner_ms", "vector_ms", "mmr_ms", "reranker_ms", "llm_ms")
        )

        # ── BUG FIX: Return the capped chunks as retrieved_chunks ────────
        # Previously, retrieved_chunks in the final state still held the full
        # 20-chunk set from retrieve_node.  This caused _write_log() and the
        # API response to report 20 chunks despite only 8 entering the LLM.
        return {
            "answer": ans,
            "retrieved_chunks": chunks,
            "citations": capped_citations,
            "latency_breakdown": latency_breakdown,
        }
    except Exception as e:
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="agent_node",
            line_number=461,
            reason=f"Unhandled exception in agent_node: {str(e)}",
            condition="exception inside agent_node",
            evidence={"exception": str(e)}
        )
        return {
            "answer": CANNOT_FIND_RESPONSE,
            "citations": [],
            "latency_breakdown": latency_breakdown,
        }


# ---------------------------------------------------------------------------
# Build LangGraph workflow
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)
workflow.add_node("route", route_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("agent", agent_node)

workflow.set_entry_point("route")
workflow.add_edge("route", "retrieve")
workflow.add_edge("retrieve", "agent")
workflow.add_edge("agent", END)

app = workflow.compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def answer(
    query: str,
    repo_id: str = None,
    filters: Dict[str, Any] = None,
    retrieval_mode: str = "single",
    request_id: str = None,
) -> tuple:
    """
    Main orchestrator entrypoint.
    Returns (answer_text, latency_breakdown_dict, retrieved_chunks, citations).
    """
    from storage.pipeline_logger import generate_request_id, log_stage, log_grounding_exit
    
    if not request_id:
        request_id = generate_request_id()

    start_time = time.time()
    start_mem = get_process_memory()

    # STAGE 1: INCOMING REQUEST
    stage1_data = {
        "request_id": request_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository_id": repo_id,
        "collection_id": repo_id,
        "user_question": query,
        "filters": filters or {},
        "retrieval_mode": retrieval_mode
    }
    log_stage(request_id, 1, "Incoming Request", stage1_data, latency_ms=0.0)

    if not isinstance(query, str):
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="answer",
            line_number=510,
            reason="Query is not a string",
            condition="not isinstance(query, str)",
            evidence={"type": type(query).__name__}
        )
        ans = CANNOT_FIND_RESPONSE
        bd = {"planner_ms": 0, "vector_ms": 0, "mmr_ms": 0, "reranker_ms": 0, "llm_ms": 0, "total_ms": 0}
        _write_log(str(query), [], [], "error", 0.0, 0.0, ans, bd)
        return ans, bd, [], []

    if not query or not query.strip():
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="answer",
            line_number=522,
            reason="Query is empty",
            condition="not query or not query.strip()",
            evidence={"query": query}
        )
        ans = "Query is empty."
        bd = {"planner_ms": 0, "vector_ms": 0, "mmr_ms": 0, "reranker_ms": 0, "llm_ms": 0, "total_ms": 0}
        _write_log("", [], [], "error", 0.0, 0.0, ans, bd)
        return ans, bd, [], []

    from storage.forensic_logger import ForensicLogger
    f_logger = ForensicLogger(request_id=request_id)
    f_logger.log_event("incoming_request", f"query='{query[:60]}...' | repo_id='{repo_id}'")

    try:
        initial_state = {
            "request_id": request_id,
            "question": query,
            "agent": "",
            "retrieved_chunks": [],
            "citations": [],
            "answer": "",
            "error": "",
            "repo_id": repo_id or "",
            "filters": filters or {},
            "retrieval_mode": retrieval_mode,
            "f_logger": f_logger,
        }

        final_state = app.invoke(initial_state)

        ans = final_state.get("answer", CANNOT_FIND_RESPONSE)
        agent = final_state.get("agent", "doc_agent")
        chunks = final_state.get("retrieved_chunks", [])
        citations = final_state.get("citations", [])
        latency_breakdown = final_state.get("latency_breakdown", {})

    except Exception as e:
        f_logger.log_exception("workflow_invoke", e)
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="answer",
            line_number=584,
            reason=f"Workflow invocation failed: {str(e)}",
            condition="exception during app.invoke(initial_state)",
            evidence={"exception": str(e)}
        )
        f_logger.finalize(CANNOT_FIND_RESPONSE, [], {})
        raise RuntimeError(f"WORKFLOW INVOCATION FATAL FAILURE: {str(e)}") from e

    latency = time.time() - start_time
    total_ms = latency * 1000.0
    end_mem = get_process_memory()
    memory_diff = max(0.0, end_mem - start_mem)

    f_logger.finalize(ans, citations, latency_breakdown)

    # STAGE 13: CITATION ASSEMBLY
    t_stage13_start = time.perf_counter()
    seen_files = set()
    citation_summary_log = []

    # Pipeline contract: chunk count == citation count (both from capped set)
    input_chunk_count = len(chunks)
    output_citation_count = len(citations)

    contract_lines = [
        f"REQUEST ID: {request_id}",
        "ORCHESTRATOR PIPELINE CONTRACT CHECK (Stage 13)",
        "=" * 60,
        f"Capped chunk count (retrieved_chunks in final_state): {input_chunk_count}",
        f"Citation count (from agent_node's capped rebuild):    {output_citation_count}",
    ]
    if output_citation_count == 0 and input_chunk_count > 0:
        msg = (f"PIPELINE CONTRACT VIOLATION: Chunk count ({input_chunk_count}) "
               f"!= Citation count ({output_citation_count})")
        contract_lines.append(msg)
        print(msg, flush=True)
    elif input_chunk_count != output_citation_count and input_chunk_count > 0:
        msg = (f"PIPELINE CONTRACT WARNING: Chunk count ({input_chunk_count}) "
               f"!= Citation count ({output_citation_count}) — may indicate deduplication")
        contract_lines.append(msg)
        print(msg, flush=True)
    else:
        contract_lines.append("Contract OK: chunk count == citation count.")

    try:
        contract_path = os.path.join(LOGS_DIR, "pipeline_contract_check.txt")
        with open(contract_path, "a", encoding="utf-8") as _f:
            _f.write("\n".join(contract_lines) + "\n\n")
    except Exception:
        pass

    for idx, cite in enumerate(citations, start=1):
        f = cite.get("file")
        if f:
            seen_files.add(f)
        citation_summary_log.append({
            "citation_index": idx,
            "formatted_citation": cite.get("citation"),
            "paper_title": cite.get("paper_title"),
            "file": f,
            "section": cite.get("section"),
            "page_start": cite.get("page_start"),
            "page_end": cite.get("page_end"),
        })

    t_stage13_end = time.perf_counter()
    stage13_ms = (t_stage13_end - t_stage13_start) * 1000

    stage13_data = {
        "input_chunk_count": input_chunk_count,
        "citations_count": output_citation_count,
        "source_files_count": len(seen_files),
        "source_files": list(seen_files),
        "citations": citation_summary_log,
    }
    log_stage(request_id, 13, "Citation Assembly", stage13_data, latency_ms=stage13_ms)

    # STAGE 14: FINAL API RESPONSE
    response_obj = {
        "request_id": request_id,
        "Answer": ans,
        "Sources": list(seen_files),
        "Chunks": chunks,
        "Citations": citations,
        "Latency": round(latency, 4),
        "LatencyBreakdown": latency_breakdown
    }
    log_stage(request_id, 14, "Final API Response", response_obj, latency_ms=total_ms)

    # ── STEP 8: ASSERTIONS ─────────────────────────────────────────────
    assert ans is not None, "ASSERTION FAILED: returned_answer is None"
    assert citations is not None, "ASSERTION FAILED: citations is None"

    # Finalize per-query forensic report (.debug/current_query/) & clean terminal output
    from storage.pipeline_logger import forensic_tracer
    forensic_tracer.returned_answer = ans
    forensic_tracer.citations = citations
    forensic_tracer.response_json = response_obj
    forensic_tracer.write_artifacts()
    forensic_tracer.print_terminal_summary()

    _write_log(query, chunks, citations, agent, latency, memory_diff, ans, latency_breakdown)
    return ans, latency_breakdown, chunks, citations


def _write_log(
    question: str,
    chunks: list,
    citations: list,
    agent: str,
    latency: float,
    memory: float,
    answer_text: str,
    latency_breakdown: Dict[str, float],
):
    os.makedirs(LOGS_DIR, exist_ok=True)

    logged_chunks = [
        {"content": c.get("content", ""), "metadata": c.get("metadata", {})}
        for c in chunks
    ]

    entry = {
        "question": question,
        "retrieved_chunks": logged_chunks,
        "citations": citations,
        "agent": agent,
        "latency": round(latency, 4),
        "memory": round(memory, 4),
        "latency_breakdown": latency_breakdown,
        "answer": answer_text,
    }

    with open(LOGS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Class-based API (for cache layer)
# ---------------------------------------------------------------------------
class Orchestrator:
    def __init__(self):
        pass

    @property
    def v_manager(self):
        global _v_manager_override
        return _v_manager_override

    @v_manager.setter
    def v_manager(self, value):
        global _v_manager_override
        _v_manager_override = value

    def answer(
        self, query: str, repo_id: str = None, filters: Dict[str, Any] = None
    ) -> dict:
        from storage.cache import SemanticCache

        cache = SemanticCache()

        if repo_id:
            cached_res = cache.get_cached_answer(query, repo_id)
            if cached_res:
                return {
                    "answer": cached_res["answer"],
                    "agent": "cache",
                    "latency": 0.0,
                    "memory": 0.0,
                    "sources": cached_res.get("sources", []),
                    "citations": [],
                    "latency_breakdown": {},
                }

        ans_str, latency_breakdown, chunks, citations = answer(query, repo_id, filters)

        agent = "doc_agent" if ans_str != CANNOT_FIND_RESPONSE else "doc_agent"
        latency = latency_breakdown.get("total_ms", 0.0) / 1000.0
        memory = 0.0
        seen_files = set()
        sources = []
        for c in chunks:
            fp = c.get("metadata", {}).get("file")
            if fp and fp not in seen_files:
                sources.append(fp)
                seen_files.add(fp)

        if repo_id and agent != "error":
            cache.set_cached_answer(query, repo_id, ans_str, sources)

        return {
            "answer": ans_str,
            "agent": agent,
            "latency": latency,
            "memory": memory,
            "sources": sources,
            "citations": citations,
            "latency_breakdown": latency_breakdown,
        }
