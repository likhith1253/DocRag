"""
eval.benchmark.metrics.retrieval
=================================
Retrieval quality metrics for the CodeGraphRAG benchmark.

All metrics operate on:
  retrieved_files : list[str]  — file_path values from RetrievedChunk, in rank order
  relevant_files  : list[str]  — from DatasetItem.relevant_sources

File paths are normalized (lowercase, forward slashes) before comparison
to prevent false negatives from OS path differences.

Research mapping:
  RQ1 (hybrid vs conventional): Recall@5, MRR
  RQ2 (KG ablation): Recall@5, nDCG@5
  RQ3 (AST ablation): Recall@5, MRR
  RQ4 (routing ablation): — (generation metrics primary)
  RQ5 (embedding ablation): Recall@5, MRR, MAP
  RQ7 (BM25/Hybrid): Recall@5, MRR, MAP
"""

from __future__ import annotations

import math
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Path normalization
# ---------------------------------------------------------------------------

def _normalize(path: str) -> str:
    """Normalize a file path for comparison (lowercase, forward slashes, strip)."""
    return path.replace("\\", "/").strip().lower()


def _normalize_list(paths: List[str]) -> List[str]:
    return [_normalize(p) for p in paths]


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------

def recall_at_k(
    retrieved_files: List[str],
    relevant_files: List[str],
    k: int,
) -> float:
    """
    Recall@K: fraction of relevant files found in top-K retrieved files.

    Recall@K = |relevant ∩ retrieved[:K]| / |relevant|

    Returns 0.0 if relevant_files is empty (undefined case).
    Returns 0.0 if k < 1.

    Parameters
    ----------
    retrieved_files : list[str]
        Retrieved file paths in rank order (rank 1 = index 0).
    relevant_files : list[str]
        Ground truth relevant file paths.
    k : int
        Cutoff rank.

    Returns
    -------
    float in [0, 1]
    """
    if not relevant_files or k < 1:
        return 0.0
    relevant_norm = set(_normalize_list(relevant_files))
    retrieved_norm = _normalize_list(retrieved_files[:k])
    hits = sum(1 for f in retrieved_norm if f in relevant_norm)
    return hits / len(relevant_norm)


def precision_at_k(
    retrieved_files: List[str],
    relevant_files: List[str],
    k: int,
) -> float:
    """
    Precision@K: fraction of top-K retrieved files that are relevant.

    Precision@K = |relevant ∩ retrieved[:K]| / K

    Returns 0.0 if retrieved_files is empty or k < 1.

    Parameters
    ----------
    retrieved_files : list[str]
        Retrieved file paths in rank order.
    relevant_files : list[str]
        Ground truth relevant file paths.
    k : int
        Cutoff rank.

    Returns
    -------
    float in [0, 1]
    """
    if not retrieved_files or k < 1:
        return 0.0
    relevant_norm = set(_normalize_list(relevant_files))
    retrieved_norm = _normalize_list(retrieved_files[:k])
    hits = sum(1 for f in retrieved_norm if f in relevant_norm)
    return hits / k


def mean_reciprocal_rank(
    retrieved_files: List[str],
    relevant_files: List[str],
) -> float:
    """
    Reciprocal Rank for a single query.

    RR = 1 / rank_of_first_relevant_result

    Returns 0.0 if no relevant result is found in retrieved_files.

    Note: When averaging over a dataset, call this per-query and average outside.

    Parameters
    ----------
    retrieved_files : list[str]
        Retrieved file paths in rank order.
    relevant_files : list[str]
        Ground truth relevant file paths.

    Returns
    -------
    float in [0, 1]
    """
    if not relevant_files:
        return 0.0
    relevant_norm = set(_normalize_list(relevant_files))
    for rank, path in enumerate(retrieved_files, start=1):
        if _normalize(path) in relevant_norm:
            return 1.0 / rank
    return 0.0


def average_precision(
    retrieved_files: List[str],
    relevant_files: List[str],
) -> float:
    """
    Average Precision for a single query.

    AP = (1/|R|) * Σ_{k: retrieved[k] is relevant} Precision@k

    Returns 0.0 if relevant_files is empty.

    Parameters
    ----------
    retrieved_files : list[str]
        Retrieved file paths in rank order.
    relevant_files : list[str]
        Ground truth relevant file paths.

    Returns
    -------
    float in [0, 1]
    """
    if not relevant_files:
        return 0.0
    relevant_norm = set(_normalize_list(relevant_files))
    hits = 0
    precision_sum = 0.0
    for k, path in enumerate(retrieved_files, start=1):
        if _normalize(path) in relevant_norm:
            hits += 1
            precision_sum += hits / k
    if hits == 0:
        return 0.0
    return precision_sum / len(relevant_norm)


def mean_average_precision(
    all_retrieved: List[List[str]],
    all_relevant: List[List[str]],
) -> float:
    """
    Mean Average Precision over a dataset.

    MAP = (1/|Q|) * Σ AP(q)

    Parameters
    ----------
    all_retrieved : list[list[str]]
        Retrieved file paths per query, in rank order.
    all_relevant : list[list[str]]
        Relevant file paths per query.

    Returns
    -------
    float in [0, 1]
    """
    if not all_retrieved:
        return 0.0
    aps = [
        average_precision(ret, rel)
        for ret, rel in zip(all_retrieved, all_relevant)
    ]
    return sum(aps) / len(aps)


def ndcg_at_k(
    retrieved_files: List[str],
    relevant_files: List[str],
    k: int,
) -> float:
    """
    Normalized Discounted Cumulative Gain at K.

    Uses binary relevance: 1 if file is relevant, 0 otherwise.

    nDCG@K = DCG@K / IDCG@K

    DCG@K  = Σ_{i=1}^{K} rel_i / log2(i+1)
    IDCG@K = Σ_{i=1}^{min(K,|R|)} 1 / log2(i+1)

    Returns 0.0 if relevant_files is empty or k < 1.

    Parameters
    ----------
    retrieved_files : list[str]
        Retrieved file paths in rank order.
    relevant_files : list[str]
        Ground truth relevant file paths.
    k : int
        Cutoff rank.

    Returns
    -------
    float in [0, 1]
    """
    if not relevant_files or k < 1:
        return 0.0
    relevant_norm = set(_normalize_list(relevant_files))
    retrieved_norm = _normalize_list(retrieved_files[:k])

    dcg = sum(
        (1.0 / math.log2(i + 2))
        for i, path in enumerate(retrieved_norm)
        if path in relevant_norm
    )
    ideal_hits = min(k, len(relevant_norm))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


# ---------------------------------------------------------------------------
# Aggregate computation
# ---------------------------------------------------------------------------

def compute_retrieval_metrics(
    retrieved_files: List[str],
    relevant_files: List[str],
    k_values: Optional[List[int]] = None,
) -> Dict[str, float]:
    """
    Compute all retrieval metrics for a single query.

    Parameters
    ----------
    retrieved_files : list[str]
        Retrieved file paths in rank order.
    relevant_files : list[str]
        Ground truth relevant file paths.
    k_values : list[int], optional
        K values for recall, precision, nDCG. Default: [1, 3, 5, 10].

    Returns
    -------
    dict mapping metric name to float value.
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    metrics: Dict[str, float] = {}

    for k in k_values:
        metrics[f"recall_at_{k}"] = recall_at_k(retrieved_files, relevant_files, k)
        metrics[f"precision_at_{k}"] = precision_at_k(retrieved_files, relevant_files, k)
        metrics[f"ndcg_at_{k}"] = ndcg_at_k(retrieved_files, relevant_files, k)

    metrics["mrr"] = mean_reciprocal_rank(retrieved_files, relevant_files)
    metrics["average_precision"] = average_precision(retrieved_files, relevant_files)

    return metrics


def aggregate_retrieval_metrics(
    per_query_metrics: List[Dict[str, float]],
) -> Dict[str, float]:
    """
    Aggregate per-query retrieval metrics into dataset-level averages.

    Parameters
    ----------
    per_query_metrics : list[dict]
        List of metric dicts from compute_retrieval_metrics(), one per query.

    Returns
    -------
    dict mapping metric name to mean float value across all queries.
    """
    if not per_query_metrics:
        return {}
    keys = per_query_metrics[0].keys()
    result = {}
    for key in keys:
        values = [m[key] for m in per_query_metrics if key in m]
        result[key] = sum(values) / len(values) if values else 0.0
    # MAP is mean of average_precision values
    if "average_precision" in result:
        result["map"] = result.pop("average_precision")
    return result
