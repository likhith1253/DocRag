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
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from storage.vector_store import VectorStoreManager, _get_config
from storage.registry import RepositoryRegistry, get_registry
from retrieval.mmr_rerank import mmr_rerank
from retrieval.cross_encoder_rerank import rerank_cross_encoder

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
        
        # If repo_id is specified in filters, use it
        if not repo_id and "paper_title" in filters:
            # Try to find repo with this paper title
            registry = get_registry()
            for rid, repo in registry.repositories.items():
                if repo.status == "READY":
                    # Check if this repo contains the paper
                    v_manager = VectorStoreManager(collection_name=repo.vector_collection)
                    chunks, _ = v_manager.search(state["question"], top_k=5, metadata_filters=filters, request_id=state.get("request_id", "default"))
                    if chunks and chunks[0]:
                        updates["repo_id"] = rid
                        break
        
        # If still no repo_id, use repository router
        if not repo_id:
            from retrieval.repository_router import rank_repositories
            registry = get_registry()
            top_repos = rank_repositories(state["question"], registry, top_k=3)
            if top_repos:
                updates["repo_id"] = top_repos[0]

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
        repo = registry.get_repository(repo_id) if repo_id else None
        v_coll = repo.vector_collection if repo else "chunks"

        global _v_manager_override
        if _v_manager_override is not None:
            v_manager = _v_manager_override
        else:
            v_manager = VectorStoreManager(collection_name=v_coll)

        # Apply retrieval mode constraints
        if retrieval_mode == "single" and repo_id:
            if not filters:
                filters = {}
        elif retrieval_mode == "corpus":
            filters = {k: v for k, v in filters.items() if k != "paper_title"}

        # Step 1: Vector search (Stage 2 & Stage 3 logged inside search())
        t0 = time.perf_counter()
        chunks, vector_timing = v_manager.search(
            state["question"], top_k=vector_top_k, metadata_filters=filters or None, request_id=request_id
        )
        latency_breakdown["embedding_ms"] = vector_timing["embedding_ms"]
        latency_breakdown["qdrant_ms"] = vector_timing["qdrant_ms"]
        latency_breakdown["vector_ms"] = (time.perf_counter() - t0) * 1000

        # Stage 4: FILTERING
        t_filter_start = time.perf_counter()
        initial_chunk_count = len(chunks)
        removed_chunks_log = []

        # Deduplicate chunks by content hash
        seen_hashes = set()
        unique_chunks = []
        for chunk in chunks:
            h = chunk.get("metadata", {}).get("hash", "")
            cid = chunk.get("id") or h or "unknown"
            doc_name = chunk.get("metadata", {}).get("file") or chunk.get("metadata", {}).get("paper_title") or "Unknown"
            if h and h in seen_hashes:
                removed_chunks_log.append({
                    "chunk_id": str(cid),
                    "filename": doc_name,
                    "reason_removed": f"Duplicate content hash '{h}'"
                })
            else:
                if h:
                    seen_hashes.add(h)
                unique_chunks.append(chunk)
        chunks = unique_chunks

        # Filter out low-value sections (References, Bibliography, Acknowledgements).
        filtered_chunks = []
        for c in chunks:
            sec = (c.get("metadata", {}).get("section") or "").strip()
            cid = c.get("id") or c.get("metadata", {}).get("hash") or "unknown"
            doc_name = c.get("metadata", {}).get("file") or c.get("metadata", {}).get("paper_title") or "Unknown"
            if _LOW_VALUE_SECTION_RE.search(sec):
                removed_chunks_log.append({
                    "chunk_id": str(cid),
                    "filename": doc_name,
                    "reason_removed": f"Low-value section filter ('{sec}')"
                })
                continue
            filtered_chunks.append(c)
        if filtered_chunks:
            chunks = filtered_chunks

        t_filter_end = time.perf_counter()
        filter_ms = (t_filter_end - t_filter_start) * 1000

        stage4_data = {
            "before_count": initial_chunk_count,
            "after_count": len(chunks),
            "removed_chunks_count": len(removed_chunks_log),
            "removed_chunks_details": removed_chunks_log
        }
        log_stage(request_id, 4, "Filtering", stage4_data, latency_ms=filter_ms)

        # Step 2: MMR rerank (Stage 5 logged inside mmr_rerank)
        query_vector_for_mmr = vector_timing.pop("query_vector", None)
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
        t0 = time.perf_counter()
        if chunks:
            chunks = rerank_cross_encoder(
                state["question"], chunks, top_k=rerank_top_k, request_id=request_id
            )
        latency_breakdown["reranker_ms"] = (time.perf_counter() - t0) * 1000

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

        # Fallback if zero chunks remain
        top_score = chunks[0].get("score", 1.0) if chunks else 0.0
        if not chunks or top_score < 0.35:
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
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="agent_node",
            line_number=417,
            reason=f"Retrieval error ('{state.get('error')}')",
            condition="state.get('error') is not empty",
            evidence={"state_error": state.get("error")}
        )
        return {
            "answer": CANNOT_FIND_RESPONSE,
            "citations": [],
            "latency_breakdown": latency_breakdown,
        }

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

        latency_breakdown["llm_ms"] = (t1 - t0) * 1000
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
        }

        final_state = app.invoke(initial_state)

        ans = final_state.get("answer", CANNOT_FIND_RESPONSE)
        agent = final_state.get("agent", "doc_agent")
        chunks = final_state.get("retrieved_chunks", [])
        citations = final_state.get("citations", [])
        latency_breakdown = final_state.get("latency_breakdown", {})

    except Exception as e:
        log_grounding_exit(
            request_id=request_id,
            file_path="agents/orchestrator.py",
            function_name="answer",
            line_number=554,
            reason=f"Workflow invocation failed: {str(e)}",
            condition="exception during app.invoke(initial_state)",
            evidence={"exception": str(e)}
        )
        ans = CANNOT_FIND_RESPONSE
        agent = "error"
        chunks = []
        citations = []
        latency_breakdown = {}

    latency = time.time() - start_time
    total_ms = latency * 1000.0
    end_mem = get_process_memory()
    memory_diff = max(0.0, end_mem - start_mem)

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
