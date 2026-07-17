"""
tests.test_benchmark_dataset
==============================
Unit tests for the BenchmarkDataset class, validation logic, and debug blocking.
"""

import json
import os
import tempfile
import unittest
from eval.benchmark.dataset import (
    BenchmarkDataset,
    DatasetItem,
    RepositoryEntry,
    DatasetError,
    DatasetSchemaError,
)


class TestBenchmarkDataset(unittest.TestCase):

    def setUp(self):
        # Create a temp file for saving/loading
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = os.path.join(self.temp_dir.name, "test_dataset.json")

        self.repo = RepositoryEntry(
            repo_id="test_repo",
            name="Test Repository",
            url="http://github.com/test",
            commit="abcdef123456",
            is_internal=True,
            description="Testing repo entry",
            language="python",
        )

        self.item = DatasetItem(
            id="q001",
            question="What is the answer to everything?",
            answer="42",
            category="Reasoning",
            difficulty="easy",
            relevant_sources=["source.py"],
            repo_id="test_repo",
            verified=True,
            verifier="human",
            created_at="2026-07-07T00:00:00Z",
            split="test",
            notes="Debug notes",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dataset_serialization(self):
        dataset = BenchmarkDataset(
            items=[self.item],
            repositories=[self.repo],
            description="Test dataset",
            purpose="benchmark",
        )

        # Save
        dataset.save(self.temp_file)
        self.assertTrue(os.path.exists(self.temp_file))

        # Load
        loaded = BenchmarkDataset.load(self.temp_file)
        self.assertEqual(loaded.purpose, "benchmark")
        self.assertEqual(len(loaded.items), 1)
        self.assertEqual(loaded.items[0].id, "q001")
        self.assertEqual(loaded.items[0].relevant_sources, ["source.py"])
        self.assertEqual(loaded.repositories[0].repo_id, "test_repo")

    def test_validation(self):
        # Valid dataset
        dataset = BenchmarkDataset(
            items=[self.item],
            repositories=[self.repo],
            description="Test dataset",
            purpose="benchmark",
        )
        report = dataset.validate()
        self.assertTrue(report.is_valid)

        # Invalid: missing repo reference
        invalid_item = DatasetItem(
            id="q002",
            question="Invalid repo?",
            answer="Yes",
            category="Reasoning",
            difficulty="easy",
            relevant_sources=["source.py"],
            repo_id="nonexistent_repo",
            verified=True,
            verifier="human",
            created_at="2026-07-07T00:00:00Z",
            split="test",
        )
        dataset_invalid = BenchmarkDataset(
            items=[invalid_item],
            repositories=[self.repo],
            description="Invalid dataset",
            purpose="benchmark",
        )
        report_invalid = dataset_invalid.validate()
        self.assertFalse(report_invalid.is_valid)
        self.assertTrue(any("nonexistent_repo" in err for err in report_invalid.errors))

    def test_debug_blocking(self):
        # debug purpose dataset
        dataset = BenchmarkDataset(
            items=[self.item],
            repositories=[self.repo],
            description="Debug dataset",
            purpose="debug",
        )

        # should fail assert_is_benchmark
        with self.assertRaises(DatasetError):
            dataset.assert_is_benchmark()

        # benchmark purpose dataset should pass
        dataset_ok = BenchmarkDataset(
            items=[self.item],
            repositories=[self.repo],
            description="Benchmark dataset",
            purpose="benchmark",
        )
        try:
            dataset_ok.assert_is_benchmark()
        except DatasetError:
            self.fail("assert_is_benchmark raised DatasetError unexpectedly")


if __name__ == "__main__":
    unittest.main()
