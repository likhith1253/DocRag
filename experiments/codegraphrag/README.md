# CodeGraphRAG experiments (archived)

This directory holds an earlier experiment that was developed in the same working tree as DocRag: retrieval-augmented QA over **source-code repositories** (Tree-sitter AST chunking, a NetworkX knowledge graph, and a router that dispatched to code / data / reasoning agents). It is kept for provenance. It is **not** used by the research-paper QA system and nothing outside `experiments/` imports it.

| Path | What it is |
|------|-----------|
| `agents/` | `router.py` (keyword-rule router), `code_agent.py`, `data_agent.py`, `reasoning_agent.py`, `query_planner.py` |
| `retrieval/`, `storage/`, `ingestion/` | vector/graph/metadata-filter search, `knowledge_graph.py`, AST parser + chunker, repo loader, language detection |
| `benchmark/` | experiment harness: systems (`codegraphrag`, `no_kg`, `no_ast`, `single_agent`, `simple_rag`, `vector_only`, `bm25`, `hybrid`), metrics, artifact/integrity checks |
| `experiments_cfg/` | YAML experiment definitions (`main_comparison`, ablations) |
| `results/` | the only recorded runs: `iteration1_*` (2 runs) and `experiment_20260720_185529_edc42be3` (manifest only) |
| `run_experiment.py`, `run_all.py` | entry points |
| `tests/` | unit tests for the above |

## What the recorded results actually show

The only completed result is `results/iteration1_20260719_043233/` (and an earlier run `..._034710`): **one system (CodeGraphRAG), 5 queries, 1 run.** Recall@5 = 0.0, MRR = 0.0, token-F1 = 0.057, mean latency 2.9 s (`summary.json`). The multi-system comparison and ablations defined in `experiments_cfg/` were never completed (the `experiment_*` folder contains only a manifest and environment capture). There are therefore **no results comparing baselines**; do not cite any from this directory.

**Not reproducible as committed:** the experiment YAMLs point at `eval/benchmark_dataset.json`, which was never committed (and the harness blocks the debug dataset by design), so the benchmark cannot be re-run from this repository.

## Running (optional)

```bash
pip install -r requirements-experiments.txt
python -m pytest experiments/codegraphrag/tests          # some tests are marked `stale`/`integration` (see root README)
python experiments/codegraphrag/run_experiment.py --list-experiments
```

Module paths were rewritten from `agents.*`, `retrieval.*`, `storage.*`, `ingestion.*`, `eval.benchmark.*` to `experiments.codegraphrag.*` when this code was moved here; recorded `config_used.yaml` files under `results/` are left untouched and still show the old class paths.
