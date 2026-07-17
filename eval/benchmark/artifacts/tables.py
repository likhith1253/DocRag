"""
eval.benchmark.artifacts.tables
=================================
Generate LaTeX and CSV comparison tables from experiment results.

Generated tables (human-written paper text NOT generated here — Amendment 1):
  - main_results.tex / main_results.csv   : full system comparison
  - ablation.tex / ablation.csv           : ablation results
  - statistical_significance.tex          : p-values and effect sizes

Research mapping:
  All RQs — tables are the primary presentation format for reported metrics.
"""

from __future__ import annotations

import csv
import json
import math
import os
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Formatting utilities
# ---------------------------------------------------------------------------

def _fmt(value: Any, decimals: int = 3, bold: bool = False, dagger: bool = False) -> str:
    """Format a metric value for LaTeX output."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        cell = "--"
    elif isinstance(value, float):
        cell = f"{value:.{decimals}f}"
    else:
        cell = str(value)
    if bold:
        cell = f"\\textbf{{{cell}}}"
    if dagger:
        cell = f"{cell}$^\\dagger$"
    return cell


def _find_best(
    systems: List[str],
    metric_values: Dict[str, float],
    higher_is_better: bool = True,
) -> str:
    """Find the system with the best value for a metric."""
    valid = {s: v for s, v in metric_values.items() if s in systems and v is not None and not (isinstance(v, float) and math.isnan(v))}
    if not valid:
        return ""
    if higher_is_better:
        return max(valid, key=valid.get)
    else:
        return min(valid, key=valid.get)


# ---------------------------------------------------------------------------
# Main table generation
# ---------------------------------------------------------------------------

def generate_main_results_table(
    per_system_metrics: Dict[str, Dict[str, float]],
    statistical_tests: Optional[Dict[str, Dict[str, Any]]] = None,
    baseline_name: str = "SimpleRAG",
    metrics_to_show: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate the main results comparison table.

    Parameters
    ----------
    per_system_metrics : dict[system_name, {metric: value}]
        Aggregate metrics per system.
    statistical_tests : dict, optional
        Wilcoxon test results per system per metric.
    baseline_name : str
        Baseline system name for significance marking.
    metrics_to_show : list[str], optional
        Which metrics to include. Default: key retrieval + generation metrics.
    output_dir : str, optional
        If provided, writes .tex and .csv files here.

    Returns
    -------
    dict with "latex" and "csv" keys containing the table strings.
    """
    if metrics_to_show is None:
        metrics_to_show = [
            "recall_at_5", "mrr", "ndcg_at_5",
            "token_f1", "semantic_similarity", "rouge_l",
            "mean_s", "p95_s",
        ]

    systems = list(per_system_metrics.keys())

    # Determine best values per metric (for bolding)
    latency_metrics = {"mean_s", "median_s", "p95_s", "p99_s"}
    best_per_metric: Dict[str, str] = {}
    for metric in metrics_to_show:
        metric_values = {s: per_system_metrics[s].get(metric, float("nan")) for s in systems}
        higher = metric not in latency_metrics
        best_per_metric[metric] = _find_best(systems, metric_values, higher_is_better=higher)

    # --- LaTeX table ---
    col_labels = {
        "recall_at_5": "R@5",
        "recall_at_1": "R@1",
        "recall_at_3": "R@3",
        "recall_at_10": "R@10",
        "mrr": "MRR",
        "map": "MAP",
        "ndcg_at_5": "nDCG@5",
        "exact_match": "EM",
        "token_f1": "Token F1",
        "semantic_similarity": "Sem.Sim",
        "rouge_l": "ROUGE-L",
        "bleu": "BLEU",
        "mean_s": "Lat.Mean",
        "median_s": "Lat.Med",
        "p95_s": "P95",
        "p99_s": "P99",
        "peak_mb": "PeakRAM",
    }

    header_cols = " & ".join(col_labels.get(m, m) for m in metrics_to_show)
    col_format = "l" + "c" * len(metrics_to_show)

    latex_rows = []
    for sys_name in systems:
        row_cells = [sys_name.replace("_", r"\_")]
        for metric in metrics_to_show:
            val = per_system_metrics[sys_name].get(metric, float("nan"))
            is_best = best_per_metric.get(metric) == sys_name
            # Check significance vs baseline
            is_significant = False
            if statistical_tests and sys_name in statistical_tests and metric in statistical_tests[sys_name]:
                test = statistical_tests[sys_name][metric]
                if isinstance(test, dict):
                    is_significant = test.get("significant", False) and sys_name != baseline_name
            cell = _fmt(val, bold=is_best, dagger=is_significant)
            row_cells.append(cell)
        latex_rows.append(" & ".join(row_cells) + r" \\")

    latex = "\n".join([
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Main comparison results. Best values in \textbf{bold}. ",
        r"$\dagger$ = statistically significant vs. " + baseline_name.replace("_", r"\_") +
        r" ($p < 0.05$, Wilcoxon signed-rank, Bonferroni corrected).}",
        r"\begin{tabular}{" + col_format + r"}",
        r"\toprule",
        f"System & {header_cols} \\\\",
        r"\midrule",
        *latex_rows,
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    # --- CSV table ---
    csv_lines = ["System," + ",".join(metrics_to_show)]
    for sys_name in systems:
        row = [sys_name]
        for metric in metrics_to_show:
            val = per_system_metrics[sys_name].get(metric, float("nan"))
            row.append(f"{val:.4f}" if isinstance(val, float) and not math.isnan(val) else "")
        csv_lines.append(",".join(row))
    csv_str = "\n".join(csv_lines)

    if output_dir:
        tables_dir = os.path.join(output_dir, "tables")
        os.makedirs(tables_dir, exist_ok=True)
        with open(os.path.join(tables_dir, "main_results.tex"), "w", encoding="utf-8") as f:
            f.write(latex)
        with open(os.path.join(tables_dir, "main_results.csv"), "w", encoding="utf-8") as f:
            f.write(csv_str)

    return {"latex": latex, "csv": csv_str}


def generate_ablation_table(
    ablation_metrics: Dict[str, Dict[str, float]],
    ablation_name: str = "ablation",
    metrics_to_show: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate ablation results table.

    Parameters
    ----------
    ablation_metrics : dict[variant_name, {metric: value}]
    ablation_name : str
        Short identifier for the table name.
    metrics_to_show : list[str], optional
    output_dir : str, optional

    Returns
    -------
    dict with "latex" and "csv".
    """
    if metrics_to_show is None:
        metrics_to_show = ["recall_at_5", "mrr", "token_f1", "mean_s"]

    result = generate_main_results_table(
        per_system_metrics=ablation_metrics,
        metrics_to_show=metrics_to_show,
        output_dir=None,
    )
    if output_dir:
        tables_dir = os.path.join(output_dir, "tables")
        os.makedirs(tables_dir, exist_ok=True)
        with open(os.path.join(tables_dir, f"{ablation_name}.tex"), "w", encoding="utf-8") as f:
            f.write(result["latex"])
        with open(os.path.join(tables_dir, f"{ablation_name}.csv"), "w", encoding="utf-8") as f:
            f.write(result["csv"])

    return result


def generate_tables(
    per_system_metrics: Dict[str, Dict[str, float]],
    output_dir: str,
    statistical_tests: Optional[Dict] = None,
    baseline_name: str = "SimpleRAG",
) -> None:
    """
    Generate all standard tables for an experiment run.

    Parameters
    ----------
    per_system_metrics : dict[system_name, {metric: value}]
    output_dir : str
        Experiment output root directory.
    statistical_tests : dict, optional
    baseline_name : str
    """
    generate_main_results_table(
        per_system_metrics=per_system_metrics,
        statistical_tests=statistical_tests,
        baseline_name=baseline_name,
        output_dir=output_dir,
    )
