"""
eval.benchmark — Research-grade evaluation framework for CodeGraphRAG.

Components:
  interface   — Abstract RetrievalSystem, RetrievedChunk, SystemResponse
  dataset     — BenchmarkDataset, DatasetItem (supports internal + external repos)
  evaluator   — BenchmarkEvaluator (main orchestrator)
  metrics/    — Retrieval, Generation, System, Statistical
  systems/    — Concrete adapters (CodeGraphRAG + all baselines)
  artifacts/  — Tables, Figures, Environment snapshot, Error analysis, Manifest, Integrity
"""
