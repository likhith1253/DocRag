# Lessons Learned Logbook

## Lesson 1: Inspect Retrieved Chunks Before Modifying Retrieval Algorithms
- **Observation**: Queries were failing due to missing context in generated answers.
- **Root Cause**: The parser font-size threshold (1.10x) misidentified standard bold text as section titles, segmenting text into micro-chunks and dropping heading labels.
- **Takeaway**: Always inspect raw chunk boundaries and parser output before tuning vector similarity or reranking hyperparameters.

## Lesson 2: Router Cache Invalidation on Re-indexing
- **Observation**: Re-indexing papers did not update collection routing choices.
- **Root Cause**: The repository router cached collection metadata globally without invalidation hooks when `worker.py` re-indexed papers.
- **Takeaway**: Always add cache invalidation hooks (`invalidate_router_cache()`) into indexing worker loops.

## Lesson 3: Cross-Encoder Type Preference Balancing
- **Observation**: Reranker gave excessive weight to generic claim types, pushing true semantic matches down the candidate list.
- **Root Cause**: Reranker type-preference boost was set to 30%, which overpowered similarity score differentials.
- **Takeaway**: Keep domain metadata weights strictly auxiliary (<= 15%) relative to dense semantic similarity scores.
