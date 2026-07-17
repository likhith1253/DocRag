"""
eval.benchmark.metrics.statistical
====================================
Statistical analysis for multi-run experiments.

Implements (Amendment 8):
  - Bootstrap confidence intervals (non-parametric, no Gaussian assumption)
  - Wilcoxon signed-rank test (paired, non-parametric, correct for ordinal data)
  - Cohen's d effect size
  - Per-system mean ± stddev over N runs

Why these choices:
  - Bootstrap CI: does not assume normality; robust for small N (n_runs=3).
  - Wilcoxon: paired (same questions, different systems), non-parametric.
    Preferred over paired t-test because metric distributions may be bimodal
    (0 or 1 per query). Bonferroni correction applied for multiple comparisons.
  - Cohen's d: standardized effect size, independent of sample size, useful
    for comparing improvement magnitude across experiments.

Research mapping:
  All RQs — every reported comparison includes CI and significance test.
"""

from __future__ import annotations

import math
import random
from typing import List, Dict, Any, Tuple, Optional


# ---------------------------------------------------------------------------
# Bootstrap confidence interval
# ---------------------------------------------------------------------------

def bootstrap_ci(
    values: List[float],
    confidence: float = 0.95,
    n_resamples: int = 1000,
    seed: int = 42,
) -> Tuple[float, float]:
    """
    Bootstrap confidence interval for the mean.

    Parameters
    ----------
    values : list[float]
        Sample values (e.g., per-query metric scores over one run).
    confidence : float
        Confidence level (default 0.95 → 95% CI).
    n_resamples : int
        Number of bootstrap resamples (default 1000).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    (lower, upper) confidence interval bounds.
    """
    if not values:
        return (float("nan"), float("nan"))

    rng = random.Random(seed)
    n = len(values)
    boot_means = []

    for _ in range(n_resamples):
        sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    alpha = 1.0 - confidence
    lower_idx = int(math.floor(alpha / 2 * n_resamples))
    upper_idx = int(math.ceil((1 - alpha / 2) * n_resamples)) - 1
    upper_idx = min(upper_idx, n_resamples - 1)

    return (boot_means[lower_idx], boot_means[upper_idx])


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank test
# ---------------------------------------------------------------------------

def wilcoxon_test(
    system_scores: List[float],
    baseline_scores: List[float],
    alternative: str = "two-sided",
) -> Dict[str, Any]:
    """
    Wilcoxon signed-rank test: tests whether system_scores > baseline_scores.

    Paired test: system_scores[i] and baseline_scores[i] must be scores on
    the same query. This assumes the same dataset in the same order was used.

    Parameters
    ----------
    system_scores : list[float]
        Per-query metric scores for the system under test.
    baseline_scores : list[float]
        Per-query metric scores for the comparison baseline.
    alternative : str
        "two-sided", "greater", or "less".

    Returns
    -------
    dict with keys: statistic, p_value, significant (p < 0.05), alternative.
    Returns {"error": ...} if scipy is unavailable.
    """
    if len(system_scores) != len(baseline_scores):
        return {"error": "Length mismatch between system_scores and baseline_scores"}
    if not system_scores:
        return {"error": "Empty input"}

    try:
        from scipy.stats import wilcoxon as scipy_wilcoxon

        differences = [s - b for s, b in zip(system_scores, baseline_scores)]
        # Remove zero differences (wilcoxon undefined for ties)
        nonzero_diffs = [d for d in differences if d != 0]

        if not nonzero_diffs:
            return {
                "statistic": float("nan"),
                "p_value": 1.0,
                "significant": False,
                "alternative": alternative,
                "note": "All differences are zero — test undefined",
            }

        stat, p_value = scipy_wilcoxon(nonzero_diffs, alternative=alternative)
        return {
            "statistic": float(stat),
            "p_value": float(p_value),
            "significant": float(p_value) < 0.05,
            "alternative": alternative,
            "n_pairs": len(nonzero_diffs),
        }
    except ImportError:
        return {"error": "scipy not installed — cannot run Wilcoxon test"}
    except Exception as e:
        return {"error": str(e)}


def bonferroni_correction(p_values: List[float]) -> List[float]:
    """
    Apply Bonferroni correction to a list of p-values.

    Corrected p = min(p * n_comparisons, 1.0)

    Use when performing multiple pairwise comparisons to control
    family-wise error rate.

    Parameters
    ----------
    p_values : list[float]
        Uncorrected p-values.

    Returns
    -------
    list[float]: Bonferroni-corrected p-values, same order as input.
    """
    n = len(p_values)
    if n == 0:
        return []
    return [min(p * n, 1.0) for p in p_values]


# ---------------------------------------------------------------------------
# Cohen's d effect size
# ---------------------------------------------------------------------------

def cohens_d(
    system_scores: List[float],
    baseline_scores: List[float],
) -> float:
    """
    Cohen's d effect size: (mean_system - mean_baseline) / pooled_std.

    Interpretation:
      |d| < 0.2  : negligible
      |d| < 0.5  : small
      |d| < 0.8  : medium
      |d| >= 0.8 : large

    Parameters
    ----------
    system_scores : list[float]
    baseline_scores : list[float]

    Returns
    -------
    float (Cohen's d). nan if pooled_std = 0.
    """
    if not system_scores or not baseline_scores:
        return float("nan")

    n1, n2 = len(system_scores), len(baseline_scores)
    mean1 = sum(system_scores) / n1
    mean2 = sum(baseline_scores) / n2

    ss1 = sum((x - mean1) ** 2 for x in system_scores)
    ss2 = sum((x - mean2) ** 2 for x in baseline_scores)

    denom = n1 + n2 - 2
    if denom > 0:
        pooled_std = math.sqrt((ss1 + ss2) / denom)
    else:
        var1 = ss1 / n1
        var2 = ss2 / n2
        pooled_std = math.sqrt((var1 + var2) / 2)

    if pooled_std == 0:
        return float("nan")

    return (mean1 - mean2) / pooled_std



def interpret_cohens_d(d: float) -> str:
    """Return a human-readable interpretation of Cohen's d."""
    if math.isnan(d):
        return "undefined"
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


# ---------------------------------------------------------------------------
# Multi-run aggregation
# ---------------------------------------------------------------------------

def aggregate_runs(
    run_metrics: List[Dict[str, float]],
) -> Dict[str, Dict[str, float]]:
    """
    Aggregate metric values across N experiment runs.

    Parameters
    ----------
    run_metrics : list[dict]
        Each dict is the aggregate metrics from one complete run.
        e.g., [{"recall_at_5": 0.72, "token_f1": 0.65}, ...]

    Returns
    -------
    dict mapping metric_name → {"mean": float, "std": float, "values": list[float]}
    """
    if not run_metrics:
        return {}

    keys = run_metrics[0].keys()
    result = {}
    for key in keys:
        values = [m[key] for m in run_metrics if key in m and not math.isnan(m.get(key, float("nan")))]
        if not values:
            result[key] = {"mean": float("nan"), "std": float("nan"), "values": []}
            continue
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = math.sqrt(variance)
        result[key] = {
            "mean": round(mean, 6),
            "std": round(std, 6),
            "values": [round(v, 6) for v in values],
        }
    return result


# ---------------------------------------------------------------------------
# Full statistical summary
# ---------------------------------------------------------------------------

def compute_statistical_summary(
    system_per_query_scores: Dict[str, List[float]],
    baseline_name: str,
    metric_name: str,
    confidence: float = 0.95,
    n_resamples: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Compute bootstrap CI, Wilcoxon test, and Cohen's d for all systems
    vs. a baseline, for one metric.

    Parameters
    ----------
    system_per_query_scores : dict[str, list[float]]
        system_name → per-query scores (e.g., recall_at_5 per query).
    baseline_name : str
        Name of the baseline system (must be in system_per_query_scores).
    metric_name : str
        Metric being analyzed (for documentation in output).
    confidence : float
        CI confidence level.
    n_resamples : int
        Bootstrap resamples.
    seed : int
        Random seed.

    Returns
    -------
    dict[system_name, {ci, wilcoxon, cohens_d, mean, ...}]
    """
    if baseline_name not in system_per_query_scores:
        return {"error": f"Baseline '{baseline_name}' not in system scores"}

    baseline_scores = system_per_query_scores[baseline_name]
    result = {}

    for sys_name, scores in system_per_query_scores.items():
        mean = sum(scores) / len(scores) if scores else float("nan")
        ci_lower, ci_upper = bootstrap_ci(scores, confidence=confidence, n_resamples=n_resamples, seed=seed)
        wilcoxon_result = wilcoxon_test(scores, baseline_scores)
        d = cohens_d(scores, baseline_scores)

        result[sys_name] = {
            "metric": metric_name,
            "mean": round(mean, 6),
            "ci_lower": round(ci_lower, 6) if not math.isnan(ci_lower) else None,
            "ci_upper": round(ci_upper, 6) if not math.isnan(ci_upper) else None,
            "wilcoxon": wilcoxon_result,
            "cohens_d": round(d, 4) if not math.isnan(d) else None,
            "cohens_d_interpretation": interpret_cohens_d(d),
            "n_queries": len(scores),
        }

    return result
