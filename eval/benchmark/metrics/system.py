"""
eval.benchmark.metrics.system
==============================
System performance metrics: latency, memory, throughput.

These are measured by the BenchmarkEvaluator, not by the systems themselves.
System adapters must NOT try to measure or set these values.

Research mapping:
  RQ6: P95 latency on CPU-only hardware (primary metric).
"""

from __future__ import annotations

import math
import platform
import time
from typing import List, Dict, Any, Optional


def compute_latency_stats(latencies_s: List[float]) -> Dict[str, float]:
    """
    Compute latency statistics from a list of per-query latencies (in seconds).

    Parameters
    ----------
    latencies_s : list[float]
        Per-query wall-clock latencies in seconds.

    Returns
    -------
    dict with keys:
        mean_s, median_s, std_s, min_s, max_s, p50_s, p75_s, p90_s, p95_s, p99_s
    """
    if not latencies_s:
        return {}

    n = len(latencies_s)
    sorted_lat = sorted(latencies_s)
    mean = sum(sorted_lat) / n
    variance = sum((x - mean) ** 2 for x in sorted_lat) / n
    std = math.sqrt(variance)

    def percentile(p: float) -> float:
        idx = (p / 100) * (n - 1)
        lower = int(idx)
        upper = min(lower + 1, n - 1)
        frac = idx - lower
        return sorted_lat[lower] * (1 - frac) + sorted_lat[upper] * frac

    return {
        "mean_s": round(mean, 4),
        "median_s": round(percentile(50), 4),
        "std_s": round(std, 4),
        "min_s": round(sorted_lat[0], 4),
        "max_s": round(sorted_lat[-1], 4),
        "p50_s": round(percentile(50), 4),
        "p75_s": round(percentile(75), 4),
        "p90_s": round(percentile(90), 4),
        "p95_s": round(percentile(95), 4),
        "p99_s": round(percentile(99), 4),
    }


def compute_memory_stats(memory_mb: List[float]) -> Dict[str, float]:
    """
    Compute memory statistics from per-query peak memory increases (in MB).

    Parameters
    ----------
    memory_mb : list[float]
        Per-query peak memory delta in MB (peak_memory_mb from SystemResponse).

    Returns
    -------
    dict with keys: mean_mb, peak_mb, std_mb
    """
    if not memory_mb:
        return {}

    n = len(memory_mb)
    mean = sum(memory_mb) / n
    peak = max(memory_mb)
    variance = sum((x - mean) ** 2 for x in memory_mb) / n
    std = math.sqrt(variance)

    return {
        "mean_mb": round(mean, 2),
        "peak_mb": round(peak, 2),
        "std_mb": round(std, 2),
    }


def compute_throughput(n_queries: int, total_wall_time_s: float) -> Dict[str, float]:
    """
    Compute throughput in queries per second.

    Parameters
    ----------
    n_queries : int
        Total number of queries processed.
    total_wall_time_s : float
        Total wall-clock time in seconds.

    Returns
    -------
    dict with keys: queries_per_second, total_wall_time_s, total_queries
    """
    qps = n_queries / total_wall_time_s if total_wall_time_s > 0 else 0.0
    return {
        "queries_per_second": round(qps, 4),
        "total_wall_time_s": round(total_wall_time_s, 2),
        "total_queries": n_queries,
    }


def compute_system_metrics(
    latencies_s: List[float],
    memory_mb: List[float],
    total_wall_time_s: Optional[float] = None,
) -> Dict[str, float]:
    """
    Compute all system metrics from raw per-query measurements.

    Parameters
    ----------
    latencies_s : list[float]
        Per-query latencies in seconds.
    memory_mb : list[float]
        Per-query peak memory deltas in MB.
    total_wall_time_s : float, optional
        Total wall-clock time. If None, uses sum of latencies.

    Returns
    -------
    dict with all latency, memory, and throughput stats.
    """
    n_queries = len(latencies_s)
    if total_wall_time_s is None:
        total_wall_time_s = sum(latencies_s)

    metrics = {}
    metrics.update(compute_latency_stats(latencies_s))
    metrics.update(compute_memory_stats(memory_mb))
    metrics.update(compute_throughput(n_queries, total_wall_time_s))
    return metrics
