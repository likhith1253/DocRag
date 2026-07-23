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
    Detects cross-paper comparison questions and sets retrieval_mode accordingly.
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
        question_lower = state["question"].lower()
        
        # Detect cross-paper comparison questions
        comparison_keywords = ["compare", "vs", "versus", "difference between", "different", "contrast", "both", "all", "each", "multiple", "several"]
        is_comparison = any(keyword in question_lower for keyword in comparison_keywords)
        
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
                # Multiple papers could answer - detect ambiguity or comparison
                # Check if the question explicitly mentions a paper
                explicit_paper = False
                for rid in top_repos:
                    repo = registry.get_repository(rid)
                    if repo and repo.name.lower() in question_lower:
                        updates["repo_id"] = rid
                        explicit_paper = True
                        break
                
                if not explicit_paper:
                    if is_comparison:
                        # Cross-paper comparison question - retrieve from all top papers
                        updates["retrieval_mode"] = "corpus"
                        # Don't set repo_id to allow corpus-wide search
                    else:
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
        
        chunks = []
        vector_timing = {"embedding_ms": 0.0, "qdrant_ms": 0.0}
        
        if retrieval_mode == "corpus":
            # Search across all ready repositories
            for rid, r in registry.repositories.items():
                if r.status == "READY" and r.vector_collection:
                    temp_vman = VectorStoreManager(collection_name=r.vector_collection)
                    c_chunks, c_timing = temp_vman.search(
                        state["question"], top_k=vector_top_k, metadata_filters=filters or None
                    )
                    chunks.extend(c_chunks)
                    vector_timing["qdrant_ms"] += c_timing.get("qdrant_ms", 0.0)
                    if "query_vector" in c_timing:
                        vector_timing["query_vector"] = c_timing["query_vector"]
                        vector_timing["embedding_ms"] = c_timing.get("embedding_ms", 0.0)
        else:
            chunks, vector_timing = v_manager.search(
                state["question"], top_k=vector_top_k, metadata_filters=filters or None
            )
            
        latency_breakdown["embedding_ms"] = vector_timing.get("embedding_ms", 0.0)
        latency_breakdown["qdrant_ms"] = vector_timing.get("qdrant_ms", 0.0)
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

        # Step 1.5: Reference Resolution
        # If any chunk mentions "Table X" or "Figure X", try to fetch it
        import re
        referenced_items = set()
        for c in chunks:
            content = c.get("content", "")
            matches = re.findall(r'(?i)\b(?:table|figure)\s*\d+\b', content)
            for m in matches:
                referenced_items.add(m.lower())
        
        if referenced_items:
            for ref in referenced_items:
                has_ref = False
                for c in chunks:
                    if ref in c.get("content", "").lower() and c.get("metadata", {}).get("chunk_type") in ["TABLE", "FIGURE"]:
                        has_ref = True
                        break
                if not has_ref:
                    # Search specifically for this reference
                    ref_chunks, _ = v_manager.search(ref, top_k=3, metadata_filters=filters or None)
                    for rc in ref_chunks:
                        if rc.get("metadata", {}).get("chunk_type") in ["TABLE", "FIGURE", "MIXED"]:
                            chunks.append(rc)
                            
        debug['post_reference_resolution_count'] = len(chunks)

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
    Implements intelligent context packing to avoid duplicates and merge related chunks.
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
        
        # Intelligent context packing
        chunks = _intelligent_context_packing(chunks)
        
        # Limit to top N chunks after intelligent packing
        chunks = chunks[:15]
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


def _intelligent_context_packing(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Intelligently pack context by:
    1. Removing duplicate chunks (by hash)
    2. Merging chunks from the same section
    3. Preferring chunks with technical content (numbers, equations, tables)
    4. Avoiding chunks from References/Bibliography
    
    Returns ordered list of chunks optimized for LLM consumption.
    """
    if not chunks:
        return []
    
    # Step 1: Remove duplicates by hash
    seen_hashes = set()
    unique_chunks = []
    for chunk in chunks:
        chunk_hash = chunk.get("metadata", {}).get("hash", "")
        if chunk_hash and chunk_hash not in seen_hashes:
            seen_hashes.add(chunk_hash)
            unique_chunks.append(chunk)
    
    # Step 2: Filter out low-value sections
    filtered_chunks = []
    for chunk in unique_chunks:
        section = (chunk.get("metadata", {}).get("section") or "").lower()
        # Skip references, bibliography, acknowledgments
        if any(x in section for x in ["reference", "bibliography", "acknowledg"]):
            continue
        filtered_chunks.append(chunk)
    
    if not filtered_chunks:
        return unique_chunks[:15]
    
    # Step 3: Score chunks by technical content
    def _technical_score(chunk: Dict[str, Any]) -> float:
        """Score chunk based on technical content."""
        content = chunk.get("content", "")
        chunk_type = chunk.get("metadata", {}).get("chunk_type", "TEXT")
        
        score = 0.0
        
        # Prefer technical chunk types
        if chunk_type == "HYPERPARAMETERS":
            score += 3.0
        elif chunk_type == "TABLE":
            score += 2.5
        elif chunk_type == "EQUATION":
            score += 2.0
        elif chunk_type == "ALGORITHM":
            score += 1.5
        elif chunk_type == "MIXED":
            score += 1.0
        
        # Bonus for numerical content
        import re
        numbers = len(re.findall(r'\d+\.?\d*', content))
        score += min(numbers * 0.1, 1.0)
        
        # Bonus for variable-value pairs
        var_pairs = len(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]\s*[0-9.]+', content))
        score += min(var_pairs * 0.5, 1.5)
        
        return score
    
    # Step 4: Sort by technical score (higher first)
    scored_chunks = [(chunk, _technical_score(chunk)) for chunk in filtered_chunks]
    scored_chunks.sort(key=lambda x: x[1], reverse=True)

    # Step 5: Re-sort to maintain section coherence.
    # Group by section and take top chunks from each section,
    # then sort sections by page_start (document reading order) not alphabetically.
    from collections import defaultdict
    section_groups = defaultdict(list)
    for chunk, score in scored_chunks:
        section = chunk.get("metadata", {}).get("section", "Unknown")
        section_groups[section].append((chunk, score))

    # Determine page_start per section (min page across all chunks in that section)
    section_page_start = {}
    for section, items in section_groups.items():
        min_page = min(
            (c.get("metadata", {}).get("page_start", 9999) for c, _ in items),
            default=9999
        )
        section_page_start[section] = min_page

    # Take top chunks from each section and merge adjacent ones
    packed_chunks = []
    for section in sorted(section_groups.keys(), key=lambda s: section_page_start.get(s, 9999)):
        section_chunks = sorted(section_groups[section], key=lambda x: x[1], reverse=True)
        top_section_chunks = [c for c, s in section_chunks[:3]]  # take top 3
        # Sort by page/line to merge
        top_section_chunks.sort(key=lambda x: x.get("metadata", {}).get("page_start", 0))

        merged_section = []
        current_merged = None
        for chunk in top_section_chunks:
            if not current_merged:
                current_merged = chunk.copy()
            else:
                # Merge if they are from the same paper and section
                c_meta = chunk.get("metadata", {})
                m_meta = current_merged.get("metadata", {})
                if c_meta.get("file") == m_meta.get("file"):
                    current_merged["content"] += "\n...\n" + chunk.get("content", "")
                    current_merged["metadata"]["page_end"] = max(m_meta.get("page_end", 0), c_meta.get("page_end", 0))
                else:
                    merged_section.append(current_merged)
                    current_merged = chunk.copy()
        if current_merged:
            merged_section.append(current_merged)

        packed_chunks.extend(merged_section)

    # If we have fewer than 15 chunks, add more from top sections
    if len(packed_chunks) < 15:
        remaining = [c for c, s in scored_chunks if c not in packed_chunks]
        packed_chunks.extend(remaining[:15 - len(packed_chunks)])

    return packed_chunks[:15]


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
