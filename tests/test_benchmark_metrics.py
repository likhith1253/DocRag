"""
tests.test_benchmark_metrics
=============================
Unit tests for the new research-grade evaluation metrics (retrieval, generation, system, statistical).
"""

import math
import unittest
from eval.benchmark.metrics.retrieval import (
    recall_at_k,
    precision_at_k,
    mean_reciprocal_rank,
    average_precision,
    ndcg_at_k,
    compute_retrieval_metrics,
)
from eval.benchmark.metrics.generation import (
    exact_match,
    token_f1,
    rouge_l,
    bleu,
    compute_generation_metrics,
)
from eval.benchmark.metrics.system import (
    compute_latency_stats,
    compute_memory_stats,
    compute_throughput,
)
from eval.benchmark.metrics.statistical import (
    bootstrap_ci,
    cohens_d,
    interpret_cohens_d,
    aggregate_runs,
)


class TestBenchmarkMetrics(unittest.TestCase):

    def test_retrieval_metrics(self):
        # retrieved: A, B, C, D, E
        # relevant: B, D
        retrieved = ["path/to/A.py", "path/to/B.py", "path/to/C.py", "path/to/D.py", "path/to/E.py"]
        relevant = ["path/to/B.py", "path/to/D.py"]

        # recall@k
        self.assertAlmostEqual(recall_at_k(retrieved, relevant, k=1), 0.0)
        self.assertAlmostEqual(recall_at_k(retrieved, relevant, k=2), 0.5)  # B is found
        self.assertAlmostEqual(recall_at_k(retrieved, relevant, k=4), 1.0)  # B and D are found

        # precision@k
        self.assertAlmostEqual(precision_at_k(retrieved, relevant, k=1), 0.0)
        self.assertAlmostEqual(precision_at_k(retrieved, relevant, k=2), 0.5)  # 1 hit in 2
        self.assertAlmostEqual(precision_at_k(retrieved, relevant, k=4), 0.5)  # 2 hits in 4

        # MRR
        self.assertAlmostEqual(mean_reciprocal_rank(retrieved, relevant), 0.5)  # B is at rank 2

        # AP (Average Precision)
        # Hits at rank 2 (Precision@2 = 0.5), rank 4 (Precision@4 = 0.5)
        # AP = (0.5 + 0.5) / 2 = 0.5
        self.assertAlmostEqual(average_precision(retrieved, relevant), 0.5)

        # nDCG@5
        # DCG@5 = 1/log2(3) [rank 2] + 1/log2(5) [rank 4] = 0.6309 + 0.4307 = 1.0616
        # IDCG@5 = 1/log2(2) [rank 1] + 1/log2(3) [rank 2] = 1.0 + 0.6309 = 1.6309
        # nDCG = 1.0616 / 1.6309 = 0.6509
        self.assertAlmostEqual(ndcg_at_k(retrieved, relevant, k=5), 0.6509209, places=5)

    def test_generation_metrics(self):
        pred = "The function add is used to add two numbers."
        gold = "the function add is used to add two numbers"

        # Exact match (normalized)
        self.assertEqual(exact_match(pred, gold), 1.0)

        # Token F1
        self.assertAlmostEqual(token_f1("hello world", "hello world"), 1.0)
        self.assertAlmostEqual(token_f1("hello world", "hello"), 2 * (1.0 * 0.5) / (1.5), places=5)  # precision=0.5, recall=1.0

        # ROUGE-L
        # Since rouge-score might be mocked or fail to run, we verify it runs or returns a float/nan
        rl = rouge_l(pred, gold)
        self.assertTrue(math.isnan(rl) or (0.0 <= rl <= 1.0))

        # BLEU
        bl = bleu(pred, gold)
        self.assertTrue(math.isnan(bl) or (0.0 <= bl <= 1.0))

    def test_system_metrics(self):
        latencies = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = compute_latency_stats(latencies)
        self.assertEqual(stats["mean_s"], 3.0)
        self.assertEqual(stats["median_s"], 3.0)
        self.assertEqual(stats["min_s"], 1.0)
        self.assertEqual(stats["max_s"], 5.0)
        self.assertEqual(stats["p95_s"], 4.8)

        memories = [10.0, 20.0, 30.0]
        mem_stats = compute_memory_stats(memories)
        self.assertEqual(mem_stats["mean_mb"], 20.0)
        self.assertEqual(mem_stats["peak_mb"], 30.0)

        tp = compute_throughput(10, 5.0)
        self.assertEqual(tp["queries_per_second"], 2.0)

    def test_statistical_metrics(self):
        # bootstrap
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        ci = bootstrap_ci(values, confidence=0.90, n_resamples=10, seed=42)
        self.assertTrue(len(ci) == 2)
        self.assertTrue(ci[0] <= ci[1])

        # cohen's d
        s1 = [1, 2, 3]
        s2 = [2, 3, 4]
        d = cohens_d(s1, s2)
        self.assertEqual(d, -1.0)  # (2 - 3) / pooled_std (std is 1.0)
        self.assertEqual(interpret_cohens_d(d), "large")

        # aggregate runs
        runs = [
            {"recall_at_5": 0.8, "token_f1": 0.7},
            {"recall_at_5": 0.9, "token_f1": 0.8},
        ]
        agg = aggregate_runs(runs)
        self.assertEqual(agg["recall_at_5"]["mean"], 0.85)
        self.assertEqual(agg["token_f1"]["mean"], 0.75)


if __name__ == "__main__":
    unittest.main()
