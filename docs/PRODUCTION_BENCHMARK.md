# Production Benchmark

## What This Is

This benchmark exercises the same production execution path used by real users:

1. `GET /health`
2. `POST /query`
3. FastAPI request validation
4. Repository resolution
5. Retrieval
6. MMR reranking
7. Cross-encoder reranking
8. Prompt construction
9. Qwen inference through the configured backend
10. JSON response serialization

The benchmark does not call internal orchestrator functions directly.

## Entry Point

Run:

```bash
python scripts/run_production_benchmark.py --base-url http://localhost:9001
```

Default dataset:

```text
eval/generated_benchmark.json
```

## Output Files

Artifacts are written to `benchmark_results/`:

- `summary.json`
- `summary.md`
- `per_question.jsonl`
- `failures.jsonl`
- `latency.csv`

## Backend Health Check

Before the benchmark starts, the runner polls `GET /health`.

If the backend exposes device metadata, the runner prints:

- `Backend Device : CUDA`
- `Backend Device : CPU`

The health response is expected to include a `backend` block with:

- `loaded`
- `device`
- `dtype`
- `model_name`

If the backend is unavailable or not loaded before the health timeout expires, the runner exits cleanly and does not execute the benchmark.

## Resume Behavior

The runner resumes from `benchmark_results/per_question.jsonl` by default.

If a question ID already exists in the file, it is skipped and not re-queried.

To force a clean run:

```bash
python scripts/run_production_benchmark.py --no-resume
```

## Failure Reporting

Each failed question is written to `failures.jsonl` with:

- Question
- Expected Answer
- Actual Answer
- Retrieved Citations
- Latency
- Failure Reason
- HTTP Response
- Repository
- Collection

## Troubleshooting

### Backend health check fails

- Verify the FastAPI backend is running.
- Confirm the configured port matches the live server.
- Check the backend logs for model loading errors.

### Benchmark returns `I cannot find...` unexpectedly

- Confirm the repository ID or collection ID in the dataset is correct.
- Check that the backend `/health` response reports `loaded: true`.
- Inspect `failures.jsonl` for the returned citations and HTTP payload.

### Benchmark is slow to start

- The backend may still be loading the model.
- Wait for `/health` to report `loaded: true`.

## HPC Usage

On the HPC cluster, run the same script:

```bash
python scripts/run_production_benchmark.py --base-url http://localhost:9001
```

The benchmark runner talks only to the running backend and does not require Streamlit.
