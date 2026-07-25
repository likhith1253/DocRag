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
import time
import json
import ctypes
import yaml
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

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
                    chunks = v_manager.search(state["question"], top_k=5, metadata_filters=filters)
                    if chunks[0]:
                        updates["repo_id"] = rid
                        break
        
        # If still no repo_id, use repository router
        if not repo_id:
            from retrieval.repository_router import rank_repositories
            registry = get_registry()
            top_repos = rank_repositories(state["question"], registry, top_k=3)
            
            if len(top_repos) > 1:
                # Multiple papers could answer - detect ambiguity
                # Check if the question explicitly mentions a paper
                question_lower = state["question"].lower()
                explicit_paper = False
                for rid in top_repos:
                    repo = registry.get_repository(rid)
                    if repo and repo.name.lower() in question_lower:
                        updates["repo_id"] = rid
                        explicit_paper = True
                        break
                
                if not explicit_paper:
                    # Ambiguous - return disambiguation message
                    paper_names = []
                    for rid in top_repos:
                        repo = registry.get_repository(rid)
                        if repo:
                            paper_names.append(repo.name)
                    
                    updates["answer"] = (
                        f"I found multiple papers that could answer this question:\n"
                        f"{chr(10).join(f'{i+1}. {name}' for i, name in enumerate(paper_names))}\n\n"
                        f"Please specify which paper you mean by including the paper name in your question."
                    )
                    updates["citations"] = []
                    return updates
            elif top_repos:
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
    KG expansion removed (not applicable to documents).
    Respects retrieval_mode: single (default), multi, corpus.
    """
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
            # Ensure we only retrieve from the specified paper
            if not filters:
                filters = {}
            # If repo has a specific paper title, enforce it
        elif retrieval_mode == "corpus":
            # Remove paper-specific filters for corpus-wide search
            filters = {k: v for k, v in filters.items() if k != "paper_title"}

        # Step 1: Vector search
        debug = {}
        debug['initial_filters'] = filters
        debug['v_coll'] = v_coll
        t0 = time.perf_counter()
        chunks, vector_timing = v_manager.search(
            state["question"], top_k=vector_top_k, metadata_filters=filters or None
        )
        latency_breakdown["embedding_ms"] = vector_timing["embedding_ms"]
        latency_breakdown["qdrant_ms"] = vector_timing["qdrant_ms"]
        latency_breakdown["vector_ms"] = (time.perf_counter() - t0) * 1000
        debug['post_vector_count'] = len(chunks)

        # Deduplicate chunks by content hash
        seen_hashes = set()
        unique_chunks = []
        for chunk in chunks:
            h = chunk.get("metadata", {}).get("hash", "")
            if h and h not in seen_hashes:
                seen_hashes.add(h)
                unique_chunks.append(chunk)
        chunks = unique_chunks
        debug['post_dedupe_count'] = len(chunks)
        # Filter out low-value sections (e.g., References/Bibliography) which often reduce concept coverage
        filtered_chunks = []
        for c in chunks:
            sec = (c.get("metadata", {}).get("section") or "").lower()
            if any(x in sec for x in ["reference", "bibliography", "acknowledg"]):
                continue
            filtered_chunks.append(c)
        if filtered_chunks:
            chunks = filtered_chunks
        debug['post_section_filter_count'] = len(chunks)

        # Step 2: MMR rerank (diversify)
        query_vector_for_mmr = vector_timing.pop("query_vector", None)
        t0 = time.perf_counter()
        if chunks:
            chunks = mmr_rerank(
                state["question"],
                chunks,
            top_k=min(40, len(chunks)),
                query_vector=query_vector_for_mmr,
            )
        latency_breakdown["mmr_ms"] = (time.perf_counter() - t0) * 1000
        debug['post_mmr_count'] = len(chunks) if chunks else 0

        # Step 3: Cross-encoder rerank (precision)
        t0 = time.perf_counter()
        if chunks:
            chunks = rerank_cross_encoder(
                state["question"], chunks, top_k=rerank_top_k
            )
        latency_breakdown["reranker_ms"] = (time.perf_counter() - t0) * 1000
        debug['post_crossencoder_count'] = len(chunks) if chunks else 0

        if not chunks:
            debug['fallback_attempted'] = True
            # Fallback: try a corpus-wide search in the global 'chunks' collection
            try:
                # First try global 'chunks' collection
                fb_vman = VectorStoreManager(collection_name='chunks')
                fb_chunks, fb_timing = fb_vman.search(state['question'], top_k=vector_top_k, metadata_filters=None)
                latency_breakdown['fallback_vector_ms'] = fb_timing.get('qdrant_ms', 0.0)
                debug['fallback_global_count'] = len(fb_chunks)
                # Deduplicate
                seen = set()
                fb_unique = []
                for ch in fb_chunks:
                    h = ch.get('metadata',{}).get('hash','')
                    if h and h not in seen:
                        seen.add(h)
                        fb_unique.append(ch)
                fb_chunks = fb_unique
                debug['fallback_global_postdedupe'] = len(fb_chunks)
                if fb_chunks:
                    query_vector_for_mmr = fb_timing.pop('query_vector', None)
                    fb_chunks = mmr_rerank(state['question'], fb_chunks, top_k=min(40, len(fb_chunks)), query_vector=query_vector_for_mmr)
                    debug['fallback_global_postmmr'] = len(fb_chunks)
                    fb_chunks = rerank_cross_encoder(state['question'], fb_chunks, top_k=rerank_top_k)
                    debug['fallback_global_postrerank'] = len(fb_chunks)
                    if fb_chunks:
                        # write debug
                        try:
                            with open(os.path.join(LOGS_DIR, 'retrieve_debug.jsonl'), 'a', encoding='utf-8') as df:
                                df.write(json.dumps(debug) + '\n')
                        except Exception:
                            pass
                        return {
                            "retrieved_chunks": fb_chunks,
                            "citations": build_citation_list(fb_chunks),
                            "latency_breakdown": latency_breakdown,
                        }
                # If that failed, brute-force search each registered collection
                # registry helper already imported at module level
                registry = get_registry()
                for rid, repo in registry.repositories.items():
                    try:
                        if not repo.vector_collection:
                            continue
                        vman = VectorStoreManager(collection_name=repo.vector_collection)
                        c_chunks, c_timing = vman.search(state['question'], top_k=min(vector_top_k,50), metadata_filters=None)
                        debug.setdefault('bruteforce', {})[rid] = len(c_chunks)
                        if not c_chunks:
                            continue
                        # dedupe
                        seen2=set(); uniq=[]
                        for ch in c_chunks:
                            h = ch.get('metadata',{}).get('hash','')
                            if h and h not in seen2:
                                seen2.add(h); uniq.append(ch)
                        c_chunks = uniq
                        qv = c_timing.pop('query_vector', None)
                        c_chunks = mmr_rerank(state['question'], c_chunks, top_k=min(20,len(c_chunks)), query_vector=qv)
                        c_chunks = rerank_cross_encoder(state['question'], c_chunks, top_k=rerank_top_k)
                        debug.setdefault('bruteforce_post', {})[rid] = len(c_chunks)
                        if c_chunks:
                            latency_breakdown['bruteforce_repo'] = repo.repo_id
                            try:
                                with open(os.path.join(LOGS_DIR, 'retrieve_debug.jsonl'), 'a', encoding='utf-8') as df:
                                    df.write(json.dumps(debug) + '\n')
                            except Exception:
                                pass
                            return {
                                "retrieved_chunks": c_chunks,
                                "citations": build_citation_list(c_chunks),
                                "latency_breakdown": latency_breakdown,
                            }
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                with open(os.path.join(LOGS_DIR, 'retrieve_debug.jsonl'), 'a', encoding='utf-8') as df:
                    df.write(json.dumps(debug) + '\n')
            except Exception:
                pass
            return {
                "retrieved_chunks": [],
                "citations": [],
                "error": "Zero chunks retrieved",
                "latency_breakdown": latency_breakdown,
            }

        try:
            with open(os.path.join(LOGS_DIR, 'retrieve_debug.jsonl'), 'a', encoding='utf-8') as df:
                df.write(json.dumps(debug) + '\n')
        except Exception:
            pass

        return {
            "retrieved_chunks": chunks,
            "citations": build_citation_list(chunks),
            "latency_breakdown": latency_breakdown,
        }
    except Exception as e:
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
    latency_breakdown = state.get("latency_breakdown", {})

    if state.get("error") == "Zero chunks retrieved":
        return {
            "answer": CANNOT_FIND_RESPONSE,
            "citations": [],
            "latency_breakdown": latency_breakdown,
        }
    elif state.get("error"):
        return {
            "answer": CANNOT_FIND_RESPONSE,
            "citations": [],
            "latency_breakdown": latency_breakdown,
        }

    try:
        chunks = state["retrieved_chunks"]
        # Limit to top N chunks to avoid context confusion but allow more context for complex questions
        chunks = chunks[:8]
        t0 = time.perf_counter()
        ans = doc_agent.run(state["question"], chunks)
        t1 = time.perf_counter()

        latency_breakdown["llm_ms"] = (t1 - t0) * 1000
        latency_breakdown["total_ms"] = sum(
            latency_breakdown.get(k, 0)
            for k in ("planner_ms", "vector_ms", "mmr_ms", "reranker_ms", "llm_ms")
        )

        return {
            "answer": ans,
            "citations": state.get("citations", []),
            "latency_breakdown": latency_breakdown,
        }
    except Exception as e:
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
) -> tuple:
    """
    Main orchestrator entrypoint.
    Returns (answer_text, latency_breakdown_dict).
    """
    start_time = time.time()
    start_mem = get_process_memory()

    if not isinstance(query, str):
        ans = CANNOT_FIND_RESPONSE
        bd = {"planner_ms": 0, "vector_ms": 0, "mmr_ms": 0, "reranker_ms": 0, "llm_ms": 0, "total_ms": 0}
        _write_log(str(query), [], [], "error", 0.0, 0.0, ans, bd)
        return ans, bd

    if not query or not query.strip():
        ans = "Query is empty."
        bd = {"planner_ms": 0, "vector_ms": 0, "mmr_ms": 0, "reranker_ms": 0, "llm_ms": 0, "total_ms": 0}
        _write_log("", [], [], "error", 0.0, 0.0, ans, bd)
        return ans, bd

    try:
        initial_state = {
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
        ans = CANNOT_FIND_RESPONSE
        agent = "error"
        chunks = []
        citations = []
        latency_breakdown = {}

    latency = time.time() - start_time
    end_mem = get_process_memory()
    memory_diff = max(0.0, end_mem - start_mem)

    _write_log(query, chunks, citations, agent, latency, memory_diff, ans, latency_breakdown)
    return ans, latency_breakdown


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

        ans_str, latency_breakdown = answer(query, repo_id, filters)

        # Read sources from log
        log_path = LOGS_PATH
        agent = "doc_agent"
        latency = 0.0
        memory = 0.0
        sources = []
        citations = []

        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    if last_entry.get("question") == query:
                        agent = last_entry.get("agent", "doc_agent")
                        latency = last_entry.get("latency", 0.0)
                        memory = last_entry.get("memory", 0.0)
                        citations = last_entry.get("citations", [])
                        seen_files = set()
                        for c in last_entry.get("retrieved_chunks", []):
                            fp = c.get("metadata", {}).get("file")
                            if fp and fp not in seen_files:
                                sources.append(fp)
                                seen_files.add(fp)
            except Exception:
                pass

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
