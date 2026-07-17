"""
tests.test_benchmark_evaluator
===============================
Integration/unit tests for the BenchmarkEvaluator orchestrating a debug run.
"""

import json
import os
import shutil
import tempfile
import unittest
import yaml
from eval.benchmark.evaluator import BenchmarkEvaluator
from eval.benchmark.dataset import BenchmarkDataset
from eval.benchmark.systems.simple_rag import SimpleRAGSystem


class TestBenchmarkEvaluator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = os.path.join(self.temp_dir.name, "results")
        self.config_path = os.path.join(self.temp_dir.name, "experiment_config.yaml")

        # Copy debug_dataset.json but make a temporary version that has purpose="benchmark"
        # so it doesn't fail the assertion, or we can test with a tiny 1-item test dataset.
        debug_dataset_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "eval", "debug_dataset.json"
        )
        with open(debug_dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Modify to be a valid benchmark dataset with only 1 item to make testing fast
        data["purpose"] = "benchmark"
        data["items"] = data["items"][:1]  # Keep only 1 item

        self.test_dataset_path = os.path.join(self.temp_dir.name, "test_benchmark_dataset.json")
        with open(self.test_dataset_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Create a temp experiment config
        config = {
            "experiment_id": "test_exp",
            "description": "Integration test config",
            "seed": 100,
            "n_runs": 1,
            "dataset": self.test_dataset_path,
            "systems": [
                {
                    "name": "SimpleRAG",
                    "class": "eval.benchmark.systems.simple_rag.SimpleRAGSystem",
                    "config_overrides": {}
                }
            ],
            "metrics": {
                "retrieval": ["recall_at_5", "mrr"],
                "generation": ["token_f1", "exact_match"],
                "system": ["mean_s"]
            },
            "statistical": {
                "confidence_level": 0.95,
                "baseline_for_comparison": "SimpleRAG"
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_experiment_flow(self):
        # We need to make sure we don't hit model generation timeout or call real model
        # if the environment isn't set up. But we can test the evaluator's orchestration
        # and mock the system's answer if needed, or run the actual SimpleRAG warm_up / retrieve.
        # Since SimpleRAG needs a Qdrant collection, it might fail if the Qdrant local files
        # don't exist. Let's mock SimpleRAGSystem.answer to return a mock response.

        evaluator = BenchmarkEvaluator(output_dir=self.output_dir)

        # Mock the system answer and retrieve method
        from unittest.mock import patch
        from eval.benchmark.interface import SystemResponse, RetrievedChunk

        mock_response = SystemResponse(
            question="What is the answer to everything?",
            answer="The answer is 42.",
            retrieved_chunks=[
                RetrievedChunk(content="The answer is 42.", file_path="config.yaml", score=0.99)
            ],
            agent="reasoning_agent",
            system_name="SimpleRAG"
        )

        with patch.object(SimpleRAGSystem, "answer", return_value=mock_response), \
             patch.object(SimpleRAGSystem, "retrieve", return_value=mock_response.retrieved_chunks), \
             patch.object(SimpleRAGSystem, "warm_up", return_value=None):

            summary = evaluator.run_experiment(self.config_path)

            self.assertEqual(summary["experiment_id"], "test_exp")
            self.assertEqual(summary["n_systems"], 1)
            self.assertEqual(summary["n_queries"], 1)

            # Check output files exist
            raw_file = os.path.join(self.output_dir, "raw", "SimpleRAG.jsonl")
            self.assertTrue(os.path.exists(raw_file))

            per_system_json = os.path.join(self.output_dir, "metrics", "per_system.json")
            self.assertTrue(os.path.exists(per_system_json))

            manifest_json = os.path.join(self.output_dir, "manifest.json")
            self.assertTrue(os.path.exists(manifest_json))

            checksums_json = os.path.join(self.output_dir, "checksums.json")
            self.assertTrue(os.path.exists(checksums_json))

            integrity_report = os.path.join(self.output_dir, "integrity_report.json")
            self.assertTrue(os.path.exists(integrity_report))

            # Verify integrity report says PASSED
            with open(integrity_report, "r") as f:
                report = json.load(f)
            self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
