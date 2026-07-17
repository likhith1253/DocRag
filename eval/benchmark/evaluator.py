"""
eval.benchmark.evaluator
==========================
BenchmarkEvaluator — the main orchestrator for all experiments.

Responsibilities:
  1. Load and validate the dataset (blocks debug datasets from experiments)
  2. Warm up each system
  3. Run each system on each query N times, measuring latency and memory
  4. Compute all metrics from raw responses
  5. Run statistical analysis
  6. Generate all artifacts (tables, figures, error analysis, environment snapshot, manifest)
  7. Run integrity verification — FAILS HARD if anything is wrong
  8. Save raw JSONL for reproducibility

Research loop compliance (Amendment 10):
  The evaluator is the "Execution" step. It is called only after:
  RQ → Hypothesis → Experiment Design → Implementation are documented.

Amendment 4 (strict integrity): verify_experiment_artifacts() is always called
after artifact generation. The experiment is not "complete" until integrity passes.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from eval.benchmark.interface import RetrievalSystem, SystemResponse
from eval.benchmark.dataset import BenchmarkDataset, DatasetItem
from eval.benchmark.metrics.retrieval import compute_retrieval_metrics, aggregate_retrieval_metrics
from eval.benchmark.metrics.generation import compute_generation_metrics, aggregate_generation_metrics
from eval.benchmark.metrics.system import compute_system_metrics
from eval.benchmark.metrics.statistical import (
    aggregate_runs,
    compute_statistical_summary,
    bonferroni_correction,
)
from eval.benchmark.artifacts.manifest import generate_manifest
from eval.benchmark.artifacts.integrity import verify_experiment_artifacts, save_checksums, _compute_file_checksum
from eval.benchmark.artifacts.environment import capture_environment, capture_seeds
from eval.benchmark.artifacts.tables import generate_tables
from eval.benchmark.artifacts.figures import generate_figures
from eval.benchmark.artifacts.error_analysis import generate_error_analysis


# ---------------------------------------------------------------------------
# Memory measurement
# ---------------------------------------------------------------------------

def _measure_memory_mb() -> float:
    """Measure current process RSS memory in MB (cross-platform)."""
    try:
        if platform.system() == "Windows":
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
        else:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        pass
    return 0.0


def _run_with_measurement(
    system: RetrievalSystem,
    question: str,
) -> SystemResponse:
    """
    Run system.answer(question) and overwrite latency_s and peak_memory_mb
    with measurements taken by the evaluator (not the system).
    """
    mem_before = _measure_memory_mb()
    t_start = time.perf_counter()

    try:
        response = system.answer(question)
    except Exception as e:
        response = SystemResponse(
            question=question,
            answer="",
            retrieved_chunks=[],
            error=str(e),
            system_name=system.name,
        )

    t_end = time.perf_counter()
    mem_after = _measure_memory_mb()

    response.latency_s = t_end - t_start
    response.peak_memory_mb = max(0.0, mem_after - mem_before)
    response.system_name = system.name
    return response


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------

class SystemResult:
    """Holds all evaluation results for one system."""

    def __init__(self, system_name: str):
        self.system_name = system_name
        # Raw: list of per-run, per-query responses
        # Shape: [run_index][query_index] → SystemResponse
        self.per_run_responses: List[List[SystemResponse]] = []
        # Aggregate metrics per run
        self.per_run_metrics: List[Dict[str, float]] = []
        # Final aggregated metrics (mean over runs)
        self.aggregate_metrics: Dict[str, Dict[str, float]] = {}
        # Per-query scores for statistical analysis (flattened over runs)
        self.per_query_scores: Dict[str, List[float]] = {}
        # Latency values per run (for boxplot)
        self.per_run_latencies: List[List[float]] = []


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------

class BenchmarkEvaluator:
    """
    Orchestrates evaluation of all systems on the benchmark dataset.

    Usage:
        evaluator = BenchmarkEvaluator(output_dir="eval/results/run1")
        result = evaluator.run_experiment(
            config_path="eval/experiments/main_comparison.yaml"
        )
    """

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._log_path = os.path.join(output_dir, "experiment_logs", "run.log")
        os.makedirs(os.path.dirname(self._log_path), exist_ok=True)

    def _log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"[{ts}] {msg}"
        print(line)
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def run_experiment(self, config_path: str, limit_override: int = None) -> Dict[str, Any]:
        """
        Run a full experiment from a YAML config file.
        """
        import yaml
        from eval.benchmark.systems import load_system

        self._log(f"Starting experiment from config: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            
        if limit_override:
            config["limit"] = limit_override

        # Save config used
        config_dir = os.path.join(self.output_dir, "experiment_logs")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "config_used.yaml"), "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False)

        # Load dataset
        dataset_path = config["dataset"]
        self._log(f"Loading dataset: {dataset_path}")
        dataset = BenchmarkDataset.load(dataset_path)

        # HARD BLOCK: reject debug datasets in experiments
        dataset.assert_is_benchmark()

        report = dataset.validate()
        if not report.is_valid:
            raise ValueError(f"Dataset validation failed:\n{report}")
        self._log(f"Dataset: {report.item_count} items, {report.split_counts}")

        dataset_hash = dataset.compute_hash()
        test_items = dataset.get_test_items()
        limit = config.get("limit")
        if limit:
            test_items = test_items[:limit]
            self._log(f"LIMITING to {limit} items for pilot run")
        self._log(f"Test items: {len(test_items)}")

        # Seeds
        base_seed = config.get("seed", 42)
        n_runs = config.get("n_runs", 3)
        run_seeds = {i: base_seed + i for i in range(n_runs)}

        # Capture environment
        env_snapshot = capture_environment(self.output_dir)
        capture_seeds(base_seed, run_seeds, self.output_dir)

        # Generate manifest
        manifest = generate_manifest(
            experiment_config=config,
            dataset_hash=dataset_hash,
            seeds={"base_seed": base_seed, "run_seeds": run_seeds},
            output_dir=self.output_dir,
        )
        if manifest.get("warnings"):
            for w in manifest["warnings"]:
                self._log(f"MANIFEST WARNING: {w}")

        # Load systems
        system_configs = config.get("systems", [])
        systems: List[RetrievalSystem] = []
        for sys_cfg in system_configs:
            sys = load_system(sys_cfg["class"], sys_cfg.get("config_overrides", {}))
            systems.append(sys)
            self._log(f"Loaded system: {sys.name}")

        # Metric config
        metric_config = config.get("metrics", {})
        retrieval_k_values = [1, 3, 5, 10]
        include_bertscore = "bertscore" in metric_config.get("optional", [])

        # Evaluate each system
        raw_dir = os.path.join(self.output_dir, "raw")
        os.makedirs(raw_dir, exist_ok=True)

        # Warm up all systems
        self._log("Warming up systems...")
        for sys in systems:
            jsonl_path = os.path.join(raw_dir, f"{sys.name}.jsonl")
            expected_records = n_runs * len(test_items)
            if os.path.exists(jsonl_path):
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    recs = [line for line in f if line.strip()]
                if len(recs) == expected_records:
                    self._log(f"  [RESUME] {sys.name} already fully evaluated. Skipping warm_up.")
                    continue

            self._log(f"  Warming up {sys.name}...")
            try:
                sys.warm_up()
            except Exception as e:
                self._log(f"  WARNING: warm_up failed for {sys.name}: {e}")

        all_system_results: Dict[str, SystemResult] = {}
        raw_records_by_system: Dict[str, List[Dict[str, Any]]] = {}

        for sys in systems:
            self._log(f"Evaluating {sys.name} ({n_runs} runs × {len(test_items)} queries)...")
            
            # Resumability check
            jsonl_path = os.path.join(raw_dir, f"{sys.name}.jsonl")
            expected_records = n_runs * len(test_items)
            if os.path.exists(jsonl_path):
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    all_responses_flat = [json.loads(line) for line in f if line.strip()]
                if len(all_responses_flat) == expected_records:
                    self._log(f"  [RESUME] Found existing completed results for {sys.name}. Skipping evaluation.")
                    result = SystemResult(sys.name)
                    runs = {i: [] for i in range(n_runs)}
                    for rec in all_responses_flat:
                        runs[rec.get("run_index", 0)].append(rec)
                    
                    per_run_recall5 = []
                    per_run_token_f1 = []
                    
                    for run_idx in range(n_runs):
                        run_recs = runs[run_idx]
                        run_latencies = [r.get("latency_s", 0.0) for r in run_recs]
                        run_mem = [r.get("peak_memory_mb", 0.0) for r in run_recs]
                        run_ret_metrics = [r.get("retrieval_metrics", {}) for r in run_recs]
                        run_gen_metrics = [r.get("generation_metrics", {}) for r in run_recs]
                        
                        per_run_recall5.append([rm.get("recall_at_5", 0.0) for rm in run_ret_metrics])
                        per_run_token_f1.append([gm.get("token_f1", 0.0) for gm in run_gen_metrics])
                        
                        agg_ret = aggregate_retrieval_metrics(run_ret_metrics)
                        agg_gen = aggregate_generation_metrics(run_gen_metrics)
                        sys_m = compute_system_metrics(run_latencies, run_mem)
                        
                        result.per_run_metrics.append({**agg_ret, **agg_gen, **sys_m})
                        result.per_run_latencies.append(run_latencies)
                        
                    result.aggregate_metrics = aggregate_runs(result.per_run_metrics)
                    result.per_query_scores = {
                        "recall_at_5": per_run_recall5[0] if per_run_recall5 else [],
                        "token_f1": per_run_token_f1[0] if per_run_token_f1 else [],
                    }
                    all_system_results[sys.name] = result
                    raw_records_by_system[sys.name] = all_responses_flat
                    continue
                else:
                    self._log(f"  [RESUME] Found partial results for {sys.name} ({len(all_responses_flat)}/{expected_records}). Re-evaluating.")

            result = SystemResult(sys.name)
            all_responses_flat: List[Dict[str, Any]] = []

            per_run_recall5: List[List[float]] = []
            per_run_token_f1: List[List[float]] = []
            per_run_latencies: List[List[float]] = []

            for run_idx in range(n_runs):
                run_seed = run_seeds[run_idx]
                random.seed(run_seed)
                self._log(f"  Run {run_idx+1}/{n_runs} (seed={run_seed})")

                # Shuffle query order (using run seed) to prevent ordering effects
                shuffled_items = list(test_items)
                rng = random.Random(run_seed)
                rng.shuffle(shuffled_items)

                run_responses: List[SystemResponse] = []
                run_ret_metrics: List[Dict[str, float]] = []
                run_gen_metrics: List[Dict[str, float]] = []
                run_latencies: List[float] = []
                run_mem: List[float] = []
                run_recall5: List[float] = []
                run_token_f1: List[float] = []

                for idx, item in enumerate(shuffled_items):
                    # Evaluation Protocol v2: Determine if this query requires LLM generation
                    run_gen = False
                    if sys.name in ["CodeGraphRAG", "SimpleRAG", "SingleAgent"]:
                        run_gen = True
                    elif sys.name == "BM25" and idx < 30: # 30-item BM25 sanity comparison
                        run_gen = True
                        
                    if run_gen:
                        response = _run_with_measurement(sys, item.question)
                    else:
                        # Retrieval only
                        mem_before = _measure_memory_mb()
                        t_start = time.perf_counter()
                        try:
                            retrieved_chunks = sys.retrieve(item.question, top_k=10)
                            error = None
                        except Exception as e:
                            retrieved_chunks = []
                            error = str(e)
                        latency = time.perf_counter() - t_start
                        mem_after = _measure_memory_mb()
                        
                        response = SystemResponse(
                            question=item.question,
                            answer="[Retrieval-Only Evaluation Bypassed LLM Generation]",
                            retrieved_chunks=retrieved_chunks,
                            latency_s=latency,
                            peak_memory_mb=max(0.0, mem_after - mem_before),
                            error=error,
                            system_name=sys.name,
                            run_index=run_idx,
                            config_snapshot=sys.configuration() if hasattr(sys, "configuration") else {}
                        )

                    response.run_index = run_idx
                    run_latencies.append(response.latency_s)
                    run_mem.append(response.peak_memory_mb)
                    run_responses.append(response)

                    # Retrieval metrics
                    retrieved_files = [c.file_path for c in response.retrieved_chunks]
                    ret_m = compute_retrieval_metrics(
                        retrieved_files, item.relevant_sources, k_values=retrieval_k_values
                    )
                    run_ret_metrics.append(ret_m)
                    run_recall5.append(ret_m.get("recall_at_5", 0.0))

                    # Generation metrics (bypassed if retrieval-only)
                    if run_gen:
                        gen_m = compute_generation_metrics(
                            predicted=response.answer,
                            expected=item.answer,
                            include_bertscore=include_bertscore,
                        )
                    else:
                        gen_m = {
                            "exact_match": 0.0,
                            "token_f1": 0.0,
                            "semantic_similarity": 0.0,
                            "rouge_l": 0.0,
                            "bleu": 0.0
                        }
                    run_gen_metrics.append(gen_m)
                    run_token_f1.append(gen_m.get("token_f1", 0.0))

                    # Build flat record for JSONL
                    record = response.to_dict()
                    record["question_id"] = item.id
                    record["expected_answer"] = item.answer
                    record["relevant_sources"] = item.relevant_sources
                    record["category"] = item.category
                    record["difficulty"] = item.difficulty
                    record["repo_id"] = item.repo_id
                    record["retrieval_metrics"] = ret_m
                    record["generation_metrics"] = gen_m
                    all_responses_flat.append(record)

                # Aggregate this run
                agg_ret = aggregate_retrieval_metrics(run_ret_metrics)
                agg_gen = aggregate_generation_metrics(run_gen_metrics)
                sys_m = compute_system_metrics(run_latencies, run_mem)
                run_metrics = {**agg_ret, **agg_gen, **sys_m}

                result.per_run_responses.append(run_responses)
                result.per_run_metrics.append(run_metrics)
                result.per_run_latencies.append(run_latencies)
                per_run_recall5.append(run_recall5)
                per_run_token_f1.append(run_token_f1)

                self._log(f"    recall@5={agg_ret.get('recall_at_5', 0):.3f}, "
                          f"token_f1={agg_gen.get('token_f1', 0):.3f}, "
                          f"mean_latency={sys_m.get('mean_s', 0):.2f}s")

            # Aggregate over runs
            result.aggregate_metrics = aggregate_runs(result.per_run_metrics)
            # Flatten per-query scores (for Wilcoxon — use first run to keep pairing)
            result.per_query_scores = {
                "recall_at_5": per_run_recall5[0] if per_run_recall5 else [],
                "token_f1": per_run_token_f1[0] if per_run_token_f1 else [],
            }
            all_system_results[sys.name] = result

            # Write JSONL
            jsonl_path = os.path.join(raw_dir, f"{sys.name}.jsonl")
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for rec in all_responses_flat:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._log(f"  Wrote {len(all_responses_flat)} records -> {jsonl_path}")
            raw_records_by_system[sys.name] = all_responses_flat

        # Teardown
        for sys in systems:
            try:
                sys.teardown()
            except Exception:
                pass

        # Build per_system mean metrics
        per_system_means: Dict[str, Dict[str, float]] = {}
        for sys_name, result in all_system_results.items():
            per_system_means[sys_name] = {
                k: v["mean"] for k, v in result.aggregate_metrics.items()
            }

        # Statistical analysis
        baseline_name = config.get("statistical", {}).get("baseline_for_comparison", "SimpleRAG")
        if baseline_name not in per_system_means and systems:
            baseline_name = systems[0].name

        stat_results = {}
        for metric in ["recall_at_5", "token_f1"]:
            per_query = {
                sys_name: result.per_query_scores.get(metric, [])
                for sys_name, result in all_system_results.items()
            }
            stat_results[metric] = compute_statistical_summary(
                system_per_query_scores=per_query,
                baseline_name=baseline_name,
                metric_name=metric,
                confidence=config.get("statistical", {}).get("confidence_level", 0.95),
                seed=base_seed,
            )

        # Save metrics
        metrics_dir = os.path.join(self.output_dir, "metrics")
        os.makedirs(metrics_dir, exist_ok=True)

        with open(os.path.join(metrics_dir, "per_system.json"), "w", encoding="utf-8") as f:
            json.dump(per_system_means, f, indent=2)

        comparison = {
            "systems": list(per_system_means.keys()),
            "baseline": baseline_name,
            "statistical_tests": stat_results,
            "per_system_means": per_system_means,
        }
        with open(os.path.join(metrics_dir, "comparison.json"), "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2)

        with open(os.path.join(metrics_dir, "statistical_tests.json"), "w", encoding="utf-8") as f:
            json.dump(stat_results, f, indent=2)

        # Generate artifacts
        self._log("Generating tables...")
        generate_tables(
            per_system_metrics=per_system_means,
            output_dir=self.output_dir,
            statistical_tests={
                sys_name: {
                    m: stat_results[m].get(sys_name, {})
                    for m in stat_results
                }
                for sys_name in per_system_means
            },
            baseline_name=baseline_name,
        )

        self._log("Generating figures...")
        all_latencies = {
            sys_name: [lat for run in result.per_run_latencies for lat in run]
            for sys_name, result in all_system_results.items()
        }
        generate_figures(
            per_system_metrics=per_system_means,
            per_query_latencies=all_latencies,
            output_dir=self.output_dir,
        )

        self._log("Generating error analysis...")
        generate_error_analysis(
            raw_records=raw_records_by_system,
            output_dir=self.output_dir,
        )

        # Save checksums of raw files
        checksums = {}
        for sys_name in all_system_results:
            jsonl_path = os.path.join(raw_dir, f"{sys_name}.jsonl")
            if os.path.exists(jsonl_path):
                checksums[f"{sys_name}.jsonl"] = _compute_file_checksum(jsonl_path)
        save_checksums(self.output_dir, checksums)

        # STRICT INTEGRITY VERIFICATION (Amendment 4)
        self._log("Running artifact integrity verification...")
        stored_for_verification = {
            sys_name: per_system_means[sys_name]
            for sys_name in per_system_means
        }
        verify_experiment_artifacts(
            output_dir=self.output_dir,
            expected_systems=list(per_system_means.keys()),
            stored_metrics=stored_for_verification,
        )
        self._log("Integrity verification PASSED.")

        summary = {
            "experiment_id": config.get("experiment_id", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_systems": len(systems),
            "n_queries": len(test_items),
            "n_runs": n_runs,
            "output_dir": self.output_dir,
            "per_system_means": per_system_means,
        }
        with open(os.path.join(self.output_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        self._log(f"Experiment complete. Results: {self.output_dir}")
        return summary
