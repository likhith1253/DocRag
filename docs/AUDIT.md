# Repository audit (2026-11-09)

## Scope and starting point

The runner exposes the requested repository at `D:\DocRag`. Branch `research-overhaul` was created from `main` at `718b33c` (`Clean up repository and improve README`). The prior local branch `overhaul/2026-10` contained work not present at that base; the task required `main`, so the branch was not imported. The base has no `pyproject.toml`; dependency ranges in `requirements.txt` are not locked.

## Architecture observed before cleanup

- `ingestion/`: PDF parsing/chunking and an indexing worker, mixed with code-repository ingestion/parser modules.
- `retrieval/`: paper matching, query analysis, MMR, cross-encoder reranking, mixed with generic code-RAG vector/graph helpers.
- `storage/`: Qdrant, registry, metadata, snapshots, progress, logging, and an unused graph store.
- `llm/`: Transformers and Ollama backends plus a backend factory.
- `agents/`: document QA/orchestration mixed with code/data/reasoning agents and a router.
- `api/`, `ui/`: FastAPI and Streamlit entry points.
- `eval/`, `scripts/`, `baselines/`, `experiments/`: multiple overlapping evaluation scripts and a separate code-RAG benchmark tree.
- `demo_dataset/`: forty tracked paper PDFs without a checked redistribution manifest.

## Findings

1. Runtime, UI, GPU, evaluation, and development dependencies were mixed in open-ended `requirements.txt`; no pinned Python version, lock file, package build config, or task runner existed.
2. Evaluation code and artifacts were duplicated. Historical acceptance checks/results are regression/debug artifacts, not research evidence. No legacy result is being used in this study.
3. Code-oriented ingestion, graph/vector search, baselines, agents, router, and benchmark systems had consumers only in their own tests/evaluation tree; they were removed together. The paper-QA paths for document parsing, retrieval, orchestration, and collection isolation remain.
4. Forty sample PDFs had no license audit. They were moved out of Git into the ignored local directory `data/source_papers_unverified/`. They remain available locally and are not treated as an established dataset.
5. The hand-authored question/answer files and evidence-bearing benchmark JSON were preserved in `data/legacy_annotations/`. They have not been independently source-verified and will not be used as frozen evaluation data without a later audit.
6. Broad `except Exception` and silent `pass` patterns remain in core modules, particularly storage, model adapters, ingestion, and orchestration. They need a focused error-handling pass before research runs.
7. Before cleanup, `pytest` collection failed because installed `pytest 8.1.0` and `pytest-asyncio 0.23.0` were incompatible (`Package` lacked `.obj`). Updating the local test tools to `pytest 9.2.0` and `pytest-asyncio 1.4.1.post1` allowed collection: 241 tests before removals and 223 after. A targeted run found stale registry expectations that bypassed the nonempty-collection safeguard; those tests now mock a nonempty collection and test empty-collection rejection directly.
8. No local V100 is available. The reported CUDA failure, quantized generation, model download/runtime, and any GPU behavior remain NOT VERIFIED.

## Current architecture after cleanup

Paper QA remains in `ingestion/pdf_parser.py`, `ingestion/doc_chunker.py`, `ingestion/worker.py`; `retrieval/` paper routing, evidence selection, MMR, and reranking; `storage/` Qdrant and repository state; `llm/`; `agents/doc_agent.py` and `agents/orchestrator.py`; API/UI. `eval/qasper_study.py` is the sole evaluation harness; the legacy HTTP benchmark was removed after this harness was introduced.

## Prioritized plan

See [PLAN.md](PLAN.md). Phase 1 ends with the cleanup-only commit. Research design, benchmark selection, frozen splits, baselines, and new features start only afterward.
