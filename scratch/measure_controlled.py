"""
Phase 6 Performance Correction: controlled measurement.
Separates cold-start, warm steady-state, and cache-hit latency so that
noise from mixing cold model-load with warm queries doesn't corrupt the
comparison (which is what happened in the original before/after benchmark).
"""
import os
import sys
import time
import json
import statistics
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from storage.registry import get_registry, RepoStatus
from storage.vector_store import VectorStoreManager
import agents.orchestrator as orchestrator


def ensure_repo():
    registry = get_registry()
    repo_id = "bench_phase6_repo"
    coll_id = f"collection_{repo_id}"
    repo = registry.get_repository(repo_id)
    if not repo:
        repo = registry.create_repository("Phase 6 Benchmark Repo", repo_id=repo_id, source_path="dataset/bench")
    registry.update_status(repo_id, RepoStatus.READY)
    vm = VectorStoreManager(collection_name=coll_id, repository_id=repo_id)
    if vm.count() == 0:
        chunks = [
            {"content": "Playing Atari with Deep Reinforcement Learning: Deep Q-Networks (DQN) use experience replay to store transitions (s, a, r, s'). Preprocessing converts 210x160 RGB frames to 84x84 grayscale and stacks the last 4 frames.",
             "metadata": {"repository_id": repo_id, "collection_id": coll_id, "paper_title": "Playing Atari with Deep Reinforcement Learning", "file": "Atari.pdf", "hash": "b_c1", "section": "1. Introduction", "page_start": 1, "page_end": 1, "contains_figure": True, "contains_equation": True, "contains_algorithm": True}},
            {"content": "Continuous Control with Deep Reinforcement Learning: DDPG adapts Q-learning to continuous action spaces using an actor-critic architecture. Bellman update equation: y = r + \\gamma Q(s', \\mu(s')).",
             "metadata": {"repository_id": repo_id, "collection_id": coll_id, "paper_title": "Continuous Control with Deep Reinforcement Learning", "file": "DDPG.pdf", "hash": "b_c2", "section": "3. Algorithm", "page_start": 3, "page_end": 3, "contains_equation": True, "contains_algorithm": True}},
            {"content": "Asynchronous Methods for Deep Reinforcement Learning: One-step Q-learning target is y = r + \\gamma \\max_{a'} Q(s', a'; \\theta^-). One-step Sarsa target is y = r + \\gamma Q(s', a'; \\theta^-) without max.",
             "metadata": {"repository_id": repo_id, "collection_id": coll_id, "paper_title": "Asynchronous Methods for Deep Reinforcement Learning", "file": "A3C.pdf", "hash": "b_c3", "section": "4. Methods", "page_start": 4, "page_end": 4, "contains_equation": True, "contains_algorithm": True}},
        ]
        vm.add_chunks(chunks)
        registry.update_status(repo_id, RepoStatus.READY)
    return repo_id


QUERIES = [
    "What does experience replay do in Atari games?",
    "What is the update equation for one-step Q-learning and how does it differ from Sarsa?",
    "What is the architecture and preprocessing in Playing Atari with Deep Reinforcement Learning?",
    "Compare Playing Atari with Deep Reinforcement Learning and Continuous Control with Deep Reinforcement Learning.",
    "What are the algorithm and equations in Continuous Control with Deep Reinforcement Learning?",
]


def run_query(repo_id, q, rid):
    t0 = time.perf_counter()
    res, bd, chunks, citations = orchestrator.answer(query=q, repo_id=repo_id, request_id=rid)
    wall = (time.perf_counter() - t0) * 1000
    bd["wall_clock_total_ms"] = wall
    return bd


def main():
    repo_id = ensure_repo()
    with patch("agents.doc_agent.generate", return_value="The model uses experience replay and deep networks with target parameters."):
        # A. COLD (this process's very first pipeline query - model already loaded by ensure_repo though;
        # true model cold start already happened above, so this is "first pipeline call" cold)
        cold = run_query(repo_id, QUERIES[0], "ctrl_cold")

        # B. WARM: same 5 distinct queries, 3 passes, to get true steady state
        passes = []
        for p in range(3):
            for i, q in enumerate(QUERIES):
                bd = run_query(repo_id, q, f"ctrl_p{p}_{i}")
                bd["query_idx"] = i
                passes.append(bd)

        # C. REPEATED IDENTICAL QUERY (embedding + CE cache hit path)
        repeated = [run_query(repo_id, QUERIES[0], f"ctrl_rep_{i}") for i in range(5)]

    def avg(rows, field):
        vals = [r.get(field, 0.0) for r in rows]
        return (sum(vals) / len(vals)) if vals else 0.0

    def med(rows, field):
        vals = [r.get(field, 0.0) for r in rows]
        return statistics.median(vals) if vals else 0.0

    fields = ["embedding_ms", "qdrant_ms", "mmr_ms", "reranker_ms", "prompt_builder_ms",
              "llm_ms", "verifier_ms", "total_ms", "wall_clock_total_ms"]

    print("\n=== A. COLD (first pipeline call after model load) ===")
    for f in fields:
        print(f"  {f:22s}: {cold.get(f, 0.0):.2f} ms")

    print("\n=== B. WARM steady-state (3 passes x 5 distinct queries, n=%d) ===" % len(passes))
    for f in fields:
        print(f"  {f:22s}: mean={avg(passes, f):7.2f} ms  median={med(passes, f):7.2f} ms")

    print("\n=== C. REPEATED IDENTICAL QUERY (cache-hit path, n=%d, first is miss) ===" % len(repeated))
    for i, r in enumerate(repeated):
        print(f"  run {i}: embedding_ms={r.get('embedding_ms', 0):.3f}  cache_hit={r.get('embedding_cache_hit')}  reranker_ms={r.get('reranker_ms', 0):.3f}  total_ms={r.get('total_ms', 0):.2f}")

    out = {
        "cold": cold,
        "warm_passes": passes,
        "repeated_identical": repeated,
    }
    with open(os.path.join(_ROOT, "scratch", "controlled_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
