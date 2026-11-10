# Cleanup log

Cleanup was performed on `research-overhaul` before research design or new benchmark work. Old evaluation outputs remain on the local machine for provenance but are untracked and ignored. Source PDFs remain locally available in the ignored unverified directory. Hand-authored QA material is retained and tracked under `data/legacy_annotations/`.

| Category | Files/directories | Action and reason | Verification |
|---|---|---|---|
| Code-RAG implementation | `baselines/`; code/data/reasoning agents, router and planner; `ingestion/chunker.py`, `loader.py`, `language_detect.py`, `parser.py`; `retrieval/vector_search.py`, `metadata_filter.py`, `graph_search.py`; `storage/knowledge_graph.py` | Removed code-repository-only functionality outside the PDF-QA pipeline. | Import search shows no remaining Python consumers. The retained test suite collects after removal. |
| Code-RAG test consumers | `tests/test_code_agent.py`, `test_data_agent.py`, `test_reasoning_agent.py`, `test_router.py`, `test_query_planner.py`, `test_phase3_dod.py`, `test_phase3_routing.py`, `test_orchestrator.py`, `test_chunker.py`, `test_loader.py`, `test_language_detect.py`, `test_parser.py`, `test_vector_search.py`, `test_metadata_filter.py`, `test_graph_search.py`, `test_knowledge_graph.py`, `test_e2e_retrieval.py`, `test_integration.py`, `test_large_integration.py`, `test_vector_store.py`, `test_escalated_e2e.py` | Removed tests coupled to retired code-RAG behavior or obsolete APIs; preserved document-QA, repository isolation, and API coverage. | Collection completed after the removals. The retained document-QA and isolation tests were run. |
| Duplicate evaluator tree | `eval/benchmark/` and its dataset, metrics, systems, artifacts, plus old evaluator/stage/archive/diagnostic scripts and generated claims | Removed duplicate harnesses and unsupported acceptance machinery. Kept only `eval/production_benchmark.py`, `eval/metrics.py`, and package init for now. | No remaining imports of `eval.benchmark`; historical metrics are not study evidence. |
| Historical outputs | `eval/results/`, `eval/artifacts/` | Removed from Git index and added ignore rules, leaving local copies untouched. | Verified the output tree remains present locally and ignored. |
| Source PDFs | `demo_dataset/` | Moved intact to ignored `data/source_papers_unverified/` pending redistribution-license review. | The files remain available locally and are absent from Git. |
| Hand-authored QA material | `eval/ai_papers_expected_answers.json`, `eval/dataset/ai_papers.json`, `eval/generated_benchmark.json` | Moved intact to `data/legacy_annotations/`; these are preserved data, not treated as validated or frozen test data. | Three JSON files remain tracked in the new location. |
| Stale docs and engineering history | `docs/archive/`, old architecture/benchmark/validation docs, `engineering/` | Removed superseded histories and claims that would conflict with the new audit. | Replaced with `AUDIT.md`, `PLAN.md`, `DECISIONS.md`, and this log. |
| One-off scripts | root `eval_ai_papers.py`, `reindex_ai_papers.py`, `run_all.py`; tracked `scripts/` contents | Removed paper-specific evaluators, diagnostics, code-RAG runners, and stale HPC scripts. New reproducibility commands will be added after architecture cleanup. | No app import references found. |
| Runtime ignore rules | databases, registries, Qdrant/graph/metadata/snapshot/log/debug/scratch/result folders, unverified source PDFs | Added ignore rules so machine-local state is not committed. | Checked tracked runtime paths and status after cleanup. |
| Registry tests | `tests/test_registry.py` | Updated stale expectations to respect the existing nonempty-vector READY safeguard; added an empty-collection failure test. | `python -m pytest -q tests/test_registry.py`: 4 passed. |



## Phase 2 test triage

- Removed `tests/test_hpc_regressions.py`: these regression assertions encoded paper-specific automatic corrections (including fabricated claim rewriting) that were removed from the general prompt/verifier. They could not test a defensible generic invariant.
- Replaced paper names in structural-intent, list-prompt, evidence retrieval, citation, and contract fixtures with synthetic study/method names. These remain behavior tests independent of benchmark-paper identities. Updated stale verifier tests to assert only generic number-risk logging and no automatic semantic rewrite.

- **Cleanup correction:** `registry.json` was still tracked despite its ignore rule. Removed it from the Git index while preserving the local registry file. Synthetic integration-test registrations were present in the local copy and will remain ignored.

| Superseded HTTP benchmark harness | `eval/production_benchmark.py`, `eval/metrics.py`, `tests/test_production_benchmark.py`, and the dead optional `StageProfiler` import in `ingestion/worker.py` | Removed after verifying the worker only referenced a missing optional module and the benchmark tests only exercised the retired HTTP harness. The frozen QASPER retrieval harness is now the single research evaluator. The worker keeps its existing stage call sites as direct calls without the profiler. | Import search shows no consumers; new QASPER harness has its own deterministic metrics and test gate.

| Uncollected manual QA utilities | `tests/test_manual_queries.py`, `tests/test_one_query_timings.py`, `tests/verification.py` | Removed: these files were not pytest tests (no collected test functions), hard-coded a stale `d:/Document_RAG` path, queried code-RAG concepts, or implemented an unused custom verification manager with broad exception swallowing. | No imports or references found; retained functional behaviors are covered by collected application tests.

| Tracked legacy evaluator outputs missed by the initial cleanup | `eval/results/` historical JSON/CSV/TEX/JSONL and plot PDFs | Removed from the Git index while preserving local copies; these generated outputs are not used as research evidence. Added the directory to ignore rules. | Confirmed no new study cites these files; current raw study runs use root `results/` with provenance metadata.
