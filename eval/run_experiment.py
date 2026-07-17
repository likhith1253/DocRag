"""
eval.run_experiment
====================
CLI entry point for running benchmark experiments.

Usage:
  python eval/run_experiment.py --config eval/experiments/main_comparison.yaml
  python eval/run_experiment.py --config eval/experiments/ablation_kg.yaml
  python eval/run_experiment.py --list-experiments
  python eval/run_experiment.py --verify-only eval/results/<dir>/

Amendment 2: Debug datasets are hard-blocked at dataset.assert_is_benchmark().
Amendment 4: Integrity verification runs automatically after every experiment.
Amendment 6: All experiment parameters come from the YAML config, not CLI flags.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Ensure project root is on path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def list_experiments() -> None:
    """Print all available experiment configs."""
    experiments_dir = os.path.join(_SCRIPT_DIR, "experiments")
    if not os.path.isdir(experiments_dir):
        print("No experiments directory found at:", experiments_dir)
        return

    import yaml
    print(f"\nAvailable experiments in {experiments_dir}:\n")
    for fname in sorted(os.listdir(experiments_dir)):
        if fname.endswith(".yaml"):
            path = os.path.join(experiments_dir, fname)
            try:
                with open(path, "r") as f:
                    cfg = yaml.safe_load(f)
                print(f"  {fname}")
                print(f"    id: {cfg.get('experiment_id', 'N/A')}")
                print(f"    description: {cfg.get('description', 'N/A')}")
                print(f"    systems: {[s['name'] for s in cfg.get('systems', [])]}")
                print(f"    n_runs: {cfg.get('n_runs', 3)}")
                print()
            except Exception as e:
                print(f"  {fname} (error reading: {e})")


def verify_only(results_dir: str) -> None:
    """
    Recompute all metrics from raw JSONL and verify consistency with stored metrics.

    This implements the Reproducibility Auditor's requirement: every metric
    must be recomputable from raw execution data alone.
    """
    from eval.benchmark.artifacts.integrity import verify_experiment_artifacts

    print(f"\nVerifying artifacts in: {results_dir}")

    # Load per_system.json to get expected systems and stored metrics
    per_system_path = os.path.join(results_dir, "metrics", "per_system.json")
    if not os.path.exists(per_system_path):
        print(f"ERROR: {per_system_path} not found. Run the experiment first.")
        sys.exit(1)

    with open(per_system_path, "r") as f:
        stored_metrics = json.load(f)

    expected_systems = list(stored_metrics.keys())

    try:
        result = verify_experiment_artifacts(
            output_dir=results_dir,
            expected_systems=expected_systems,
            stored_metrics=stored_metrics,
        )
        print(f"\nVerification PASSED")
        print(f"  Checks passed: {result['n_checks_passed']}")
        print(f"  Warnings: {result['n_warnings']}")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"  WARNING: {w}")
        report_path = os.path.join(results_dir, "integrity_report.json")
        print(f"  Full report: {report_path}")
    except Exception as e:
        print(f"\nVerification FAILED:")
        print(str(e))
        sys.exit(1)


def run_experiment(config_path: str, out_dir: str = None, limit: int = None) -> None:
    """Run an experiment from a YAML config file."""
    from eval.benchmark.evaluator import BenchmarkEvaluator
    import yaml

    if not os.path.exists(config_path):
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    if limit:
        config["limit"] = limit

    experiment_id = config.get("experiment_id", "experiment")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_dir = out_dir if out_dir else os.path.join(
        _SCRIPT_DIR, "results", f"{experiment_id}_{timestamp}"
    )

    print(f"\n{'='*60}")
    print(f"CodeGraphRAG Benchmark Experiment")
    print(f"{'='*60}")
    print(f"Experiment ID : {experiment_id}")
    print(f"Config        : {config_path}")
    print(f"Output        : {output_dir}")
    print(f"Description   : {config.get('description', 'N/A')}")
    print(f"{'='*60}\n")

    evaluator = BenchmarkEvaluator(output_dir=output_dir)
    try:
        summary = evaluator.run_experiment(config_path=config_path, limit_override=limit)
        print(f"\n{'='*60}")
        print(f"EXPERIMENT COMPLETE")
        print(f"{'='*60}")
        print(f"Results: {output_dir}")
        print(f"\nPer-system means:")
        for sys_name, metrics in summary.get("per_system_means", {}).items():
            r5 = metrics.get("recall_at_5", float("nan"))
            tf1 = metrics.get("token_f1", float("nan"))
            lat = metrics.get("mean_s", float("nan"))
            print(f"  {sys_name:25s} | R@5={r5:.3f} | Token_F1={tf1:.3f} | Lat={lat:.2f}s")
    except Exception as e:
        import traceback
        print(f"\nEXPERIMENT FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="CodeGraphRAG Benchmark Experiment Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python eval/run_experiment.py --config eval/experiments/main_comparison.yaml
  python eval/run_experiment.py --list-experiments
  python eval/run_experiment.py --verify-only eval/results/main_comparison_20260707_000000/
        """
    )
    parser.add_argument(
        "--config", type=str,
        help="Path to experiment YAML config file",
    )
    parser.add_argument(
        "--list-experiments", action="store_true",
        help="List all available experiment configurations",
    )
    parser.add_argument(
        "--verify-only", type=str, metavar="RESULTS_DIR",
        help="Verify artifacts in an existing results directory (no re-execution)",
    )

    parser.add_argument(
        "--out_dir", type=str,
        help="Optional output directory to override auto-generated timestamp dir",
    )
    parser.add_argument(
        "--limit", type=int,
        help="Limit the number of test items (useful for pilot runs)",
    )

    args = parser.parse_args()

    if args.list_experiments:
        list_experiments()
    elif args.verify_only:
        verify_only(args.verify_only)
    elif args.config:
        run_experiment(args.config, args.out_dir, args.limit)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
