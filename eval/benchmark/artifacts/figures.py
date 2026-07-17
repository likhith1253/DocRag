"""
eval.benchmark.artifacts.figures
==================================
Generate publication-quality figures from experiment results.

Figures generated (Amendment 1 — no auto-generated paper text):
  - recall_at_k_curve.pdf   : Recall@{1,3,5,10} line chart per system
  - system_comparison.pdf   : bar chart of primary metrics
  - latency_boxplot.pdf     : per-system latency distribution
  - error_category.pdf      : error breakdown by category

All figures saved as both .pdf (for paper) and .png (for quick viewing).

Research mapping:
  RQ1: system_comparison, recall_at_k_curve
  RQ6: latency_boxplot
  All: error_category
"""

from __future__ import annotations

import json
import math
import os
from typing import Dict, Any, List, Optional


# Use Agg backend to avoid display requirement on headless systems
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# ---------------------------------------------------------------------------
# Shared style
# ---------------------------------------------------------------------------

COLORS = [
    "#2563EB",  # blue
    "#DC2626",  # red
    "#16A34A",  # green
    "#D97706",  # amber
    "#7C3AED",  # violet
    "#0891B2",  # cyan
    "#BE185D",  # pink
    "#65A30D",  # lime
]

FIGURE_DPI = 150
FIGURE_FORMAT = ["pdf", "png"]


def _save_figure(fig: plt.Figure, path_without_ext: str) -> List[str]:
    """Save figure in all configured formats."""
    saved = []
    for fmt in FIGURE_FORMAT:
        full_path = f"{path_without_ext}.{fmt}"
        fig.savefig(full_path, dpi=FIGURE_DPI, bbox_inches="tight")
        saved.append(full_path)
    plt.close(fig)
    return saved


def _setup_style():
    """Apply consistent plot style."""
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 9,
        "figure.figsize": (8, 5),
    })


# ---------------------------------------------------------------------------
# Recall@K curve
# ---------------------------------------------------------------------------

def plot_recall_at_k(
    per_system_metrics: Dict[str, Dict[str, float]],
    k_values: Optional[List[int]] = None,
    output_dir: Optional[str] = None,
    title: str = "Recall@K by System",
) -> plt.Figure:
    """
    Line chart: Recall@{1,3,5,10} for each system.

    Research mapping: RQ1, RQ2, RQ3, RQ5, RQ7

    Parameters
    ----------
    per_system_metrics : dict[system_name, {metric: value}]
    k_values : list[int]
        K values to plot. Default: [1, 3, 5, 10].
    output_dir : str, optional
        If provided, saves figure here.
    title : str

    Returns
    -------
    matplotlib Figure object.
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    _setup_style()
    fig, ax = plt.subplots(figsize=(8, 5))

    systems = list(per_system_metrics.keys())
    for i, sys_name in enumerate(systems):
        recall_values = []
        for k in k_values:
            metric_name = f"recall_at_{k}"
            val = per_system_metrics[sys_name].get(metric_name, float("nan"))
            recall_values.append(val if not math.isnan(val) else None)

        valid_k = [k for k, v in zip(k_values, recall_values) if v is not None]
        valid_v = [v for v in recall_values if v is not None]

        ax.plot(
            valid_k, valid_v,
            marker="o", linewidth=2, markersize=6,
            color=COLORS[i % len(COLORS)],
            label=sys_name,
        )

    ax.set_xlabel("K")
    ax.set_ylabel("Recall@K")
    ax.set_title(title)
    ax.set_xticks(k_values)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="lower right", framealpha=0.9)
    ax.grid(True, alpha=0.5)

    if output_dir:
        figs_dir = os.path.join(output_dir, "figures")
        os.makedirs(figs_dir, exist_ok=True)
        _save_figure(fig, os.path.join(figs_dir, "recall_at_k_curve"))
    return fig


# ---------------------------------------------------------------------------
# System comparison bar chart
# ---------------------------------------------------------------------------

def plot_system_comparison(
    per_system_metrics: Dict[str, Dict[str, float]],
    metrics_to_show: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    title: str = "System Comparison",
) -> plt.Figure:
    """
    Grouped bar chart for primary metrics across all systems.

    Research mapping: RQ1, RQ4, RQ7

    Parameters
    ----------
    per_system_metrics : dict[system_name, {metric: value}]
    metrics_to_show : list[str]
        Default: ["recall_at_5", "mrr", "token_f1"].
    output_dir : str, optional
    title : str

    Returns
    -------
    matplotlib Figure.
    """
    if metrics_to_show is None:
        metrics_to_show = ["recall_at_5", "mrr", "token_f1"]

    _setup_style()
    systems = list(per_system_metrics.keys())
    n_systems = len(systems)
    n_metrics = len(metrics_to_show)

    x = np.arange(n_metrics)
    width = 0.8 / n_systems

    fig, ax = plt.subplots(figsize=(max(8, n_metrics * 2), 5))

    for i, sys_name in enumerate(systems):
        values = []
        for metric in metrics_to_show:
            val = per_system_metrics[sys_name].get(metric, float("nan"))
            values.append(val if not math.isnan(val) else 0.0)

        offset = (i - n_systems / 2 + 0.5) * width
        bars = ax.bar(
            x + offset, values, width,
            label=sys_name,
            color=COLORS[i % len(COLORS)],
            alpha=0.85,
            edgecolor="white",
        )

    metric_labels = {
        "recall_at_5": "Recall@5",
        "mrr": "MRR",
        "map": "MAP",
        "ndcg_at_5": "nDCG@5",
        "token_f1": "Token F1",
        "semantic_similarity": "Sem.Sim",
        "rouge_l": "ROUGE-L",
        "exact_match": "Exact Match",
    }

    ax.set_xlabel("Metric")
    ax.set_ylabel("Score")
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels([metric_labels.get(m, m) for m in metrics_to_show], rotation=15, ha="right")
    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper right", framealpha=0.9, fontsize=8)
    ax.grid(True, axis="y", alpha=0.5)

    if output_dir:
        figs_dir = os.path.join(output_dir, "figures")
        os.makedirs(figs_dir, exist_ok=True)
        _save_figure(fig, os.path.join(figs_dir, "system_comparison"))
    return fig


# ---------------------------------------------------------------------------
# Latency boxplot
# ---------------------------------------------------------------------------

def plot_latency_boxplot(
    per_query_latencies: Dict[str, List[float]],
    output_dir: Optional[str] = None,
    title: str = "Per-Query Latency Distribution",
) -> plt.Figure:
    """
    Box plot of per-query latency distributions per system.

    Research mapping: RQ6

    Parameters
    ----------
    per_query_latencies : dict[system_name, list[float]]
        Per-query latency values in seconds.
    output_dir : str, optional
    title : str

    Returns
    -------
    matplotlib Figure.
    """
    _setup_style()
    systems = list(per_query_latencies.keys())
    data = [per_query_latencies[s] for s in systems]

    fig, ax = plt.subplots(figsize=(max(6, len(systems) * 1.5), 5))

    bp = ax.boxplot(
        data,
        patch_artist=True,
        medianprops={"color": "black", "linewidth": 2},
        flierprops={"marker": "o", "markersize": 3, "alpha": 0.5},
    )
    ax.set_xticks(range(1, len(systems) + 1))
    ax.set_xticklabels(systems)

    for patch, color in zip(bp["boxes"], COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_xlabel("System")
    ax.set_ylabel("Latency (s)")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    ax.grid(True, axis="y", alpha=0.5)

    if output_dir:
        figs_dir = os.path.join(output_dir, "figures")
        os.makedirs(figs_dir, exist_ok=True)
        _save_figure(fig, os.path.join(figs_dir, "latency_boxplot"))
    return fig


# ---------------------------------------------------------------------------
# Main generate function
# ---------------------------------------------------------------------------

def generate_figures(
    per_system_metrics: Dict[str, Dict[str, float]],
    per_query_latencies: Optional[Dict[str, List[float]]],
    output_dir: str,
) -> None:
    """
    Generate all standard figures for an experiment run.

    Parameters
    ----------
    per_system_metrics : dict[system_name, {metric: value}]
    per_query_latencies : dict[system_name, list[float]], optional
    output_dir : str
        Experiment output root directory.
    """
    plot_recall_at_k(per_system_metrics, output_dir=output_dir)
    plot_system_comparison(per_system_metrics, output_dir=output_dir)
    if per_query_latencies:
        plot_latency_boxplot(per_query_latencies, output_dir=output_dir)
