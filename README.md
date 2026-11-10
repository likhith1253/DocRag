# DocRag: evidence retrieval for research-paper QA

DocRag is an experimental system for indexing research papers and retrieving cited evidence for questions. This repository is being prepared as a reproducible CPU-first research project. Its previous regex-based acceptance benchmark is retained only as historical regression material and is not scientific evidence.

## Research question

The primary study asks whether a simple, generic structure-aware retrieval step improves recovery of annotator-highlighted table/figure evidence on QASPER, compared with BM25, dense retrieval, reciprocal-rank fusion, cross-encoder reranking, and MMR. The full protocol and falsification criteria are in [docs/RESEARCH.md](docs/RESEARCH.md). QASPER was introduced by Dasigi et al. at NAACL 2021; the dataset release is identified by a pinned Hugging Face revision and file hashes in [data/frozen/qasper_manifest.json](data/frozen/qasper_manifest.json).

The test split is frozen and the evaluator requires an explicit `--allow-test` flag. Development runs use the official validation split. No test scores have been inspected. Results will be reported only after the validation protocol is fixed and the test harness is committed.

## Status

- The CPU-locked package, typed settings, generation cache, API/UI, and core regression tests are present. The full fast-test suite is not yet verified; see [docs/PLAN.md](docs/PLAN.md).
- Retrieval-study implementation is in progress. No research result or improvement claim is currently reported.
- The V100 generation path, external API backends, and end-to-end answer quality are **NOT VERIFIED**.
- PDFs preserved from the previous checkout have unresolved redistribution licenses and are excluded from all study runs.
- The repository has no source-code license. Do not redistribute the application as open source until ownership and licensing are reviewed. The QASPER dataset itself is identified as CC BY 4.0 by its pinned dataset card; the data are downloaded locally rather than committed.

## Setup

Requirements: Windows, Linux, or macOS; Python 3.12.5; `uv`. PyTorch is resolved from the CPU-only PyTorch index.

```bash
uv sync --locked --group dev
uv run pytest -q -m "not slow and not gpu"
uv run ruff check settings.py llm/cache.py retrieval/query_analyzer.py retrieval/paper_matcher.py eval/qasper_study.py scripts/download_qasper.py scripts/smoke_generation.py scripts/verify_cuda_generation.py tests/test_qasper_study.py
uv run mypy
```

On Windows PowerShell, use `uv.exe` and the same arguments. For the research dataset and retrieval model, network access to Hugging Face is required once.

## Reproduce the retrieval study

Download the pinned QASPER files and verify their hashes:

```bash
uv run python scripts/download_qasper.py
```

Validation-only development run (first 25 question IDs is a smoke check):

```bash
uv run python -m eval.qasper_study --split validation --systems bm25,dense,hybrid --top-k 10 --limit 25
```

Full validation run:

```bash
uv run python -m eval.qasper_study --split validation --systems bm25,dense,hybrid,rerank,mmr --top-k 10 --candidate-k 40
```

After protocol/code choices are frozen and validation is complete, one test evaluation is permitted:

```bash
uv run python -m eval.qasper_study --split test --allow-test --systems bm25,dense,hybrid,rerank,mmr --top-k 10 --candidate-k 40
```

Raw per-question rankings, metrics, configuration hash, data hash, hardware/runtime metadata, and commit are saved beneath `results/`. The current implementation does not yet implement confidence intervals or the structure-aware condition, so those commands are not a finished reproduction of the hypotheses in the protocol. Do not treat the current script output as final study results until those gaps are closed.

## Run the application

The application supports paper ingestion and retrieval through a FastAPI API and Streamlit UI. Use CPU-compatible settings by default. Model files download on first use and may require substantial RAM.

```bash
uv run uvicorn api.main:app --host 127.0.0.1 --port 9001
uv run streamlit run ui/app.py
```

Container build and run (Docker daemon required):

```bash
docker build -t docrag-research:local .
docker run --rm -p 9001:9001 -v docrag-data:/data docrag-research:local
```

The Dockerfile keeps Qdrant and registry state in `/data`. This container build could not be verified in the current session because the Docker Desktop Linux engine was unavailable.

## Architecture

```mermaid
flowchart LR
  PDF[Research paper PDF] --> PARSE[PyMuPDF extraction]
  PARSE --> CHUNK[Section-aware chunks]
  CHUNK --> EMBED[CPU sentence embeddings]
  EMBED --> STORE[Isolated Qdrant collection]
  Q[Question] --> ROUTE[Paper and evidence intent routing]
  ROUTE --> RET[Filtered retrieval and optional reranking]
  STORE --> RET
  RET --> GROUNDED[Evidence-grounded response prompt]
  GROUNDED --> LLM[Transformers or Ollama backend]
  LLM --> OUT[Answer with source metadata]
```

## Limitations

The primary experiment is a retrieval study on English NLP papers. It does not establish generality across sciences, correct parsing of all equations or diagrams, factual accuracy of generated answers, calibrated abstention, or human agreement. The current risk scanner checks selected numerical/equation mismatches; it is not a semantic claim verifier. Cross-paper comparison and model-generation behavior are product features, not validated research findings. See [docs/DECISIONS.md](docs/DECISIONS.md) and [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md) for current progress and unverified items.

## References

- Dasigi, Pradeep, Kyle Lo, Iz Beltagy, Arman Cohan, Noah A. Smith, and Matt Gardner. 2021. [A Dataset of Information-Seeking Questions and Answers Anchored in Research Papers](https://aclanthology.org/2021.naacl-main.365/). NAACL-HLT, 4599–4610. DOI: 10.18653/v1/2021.naacl-main.365.
