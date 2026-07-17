# Performance Baseline Strategy

Before optimizations begin in Phase 1, we must establish a performance baseline against the frozen research prototype. 

## 1. Metrics to Capture

For every benchmark query, we will record:
1. **End-to-End Latency** (wall-clock time from request to response).
2. **Retrieval Latency** (time taken by Qdrant + Reranker).
3. **Graph Traversal Latency** (time taken to hop edges in the graph).
4. **LLM Generation Latency** (time taken by Ollama/Transformers).
5. **Peak Memory Usage** (Resident Set Size).
6. **Disk IO** (bytes read/written during query).

## 2. The Verification Loop

As per the Tiered Verification Strategy:
- **Level 1**: Runs a single benchmark query. Must not exceed baseline latency.
- **Level 2**: Runs 10 queries at the end of each phase. Averages are compared against the baseline.
- **Rollback Condition**: If any architectural change (e.g., singleton introduction, caching) causes the average latency to increase, or memory to leak, the change must be rolled back and a new approach engineered.

## 3. Baseline Execution
*(To be populated post-Phase 2 after the Latency Profiler generates the initial `LATENCY_PROFILE.csv` using the research code).*
