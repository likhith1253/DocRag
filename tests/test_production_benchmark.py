import json
import socket
from pathlib import Path

from eval.production_benchmark import (
    BenchmarkAPIClient,
    BenchmarkConfig,
    ProductionBenchmarkRunner,
    aggregate_records,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


def test_http_client_retries_and_parses_health():
    calls = {"count": 0}

    def opener(req, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise socket.timeout("timed out")
        return _FakeResponse(
            {
                "status": "ok",
                "backend": {
                    "loaded": True,
                    "device": "cuda",
                    "dtype": "float16",
                    "model_name": "Qwen/Qwen2.5-3B-Instruct",
                },
            }
        )

    client = BenchmarkAPIClient(
        "http://localhost:9001",
        timeout_s=1.0,
        retries=2,
        retry_backoff_s=0.0,
        opener=opener,
    )

    health = client.health()
    assert health["status"] == "ok"
    assert health["backend"]["device"] == "cuda"
    assert calls["count"] == 2


def test_runner_writes_outputs_and_supports_resume(tmp_path):
    dataset_path = tmp_path / "dataset.json"
    output_dir = tmp_path / "benchmark_results"

    dataset = [
        {
            "id": "Q1",
            "question": "What is the API called?",
            "expected_answer": "The API is called DocumentRAG.",
            "repo_id": "repo-1",
            "paper": "paper-a.pdf",
            "key_concepts": ["DocumentRAG", "API"],
        },
        {
            "id": "Q2",
            "question": "What does the system use?",
            "expected_answer": "The system uses Qwen.",
            "repo_id": "repo-1",
            "paper": "paper-a.pdf",
            "key_concepts": ["Qwen"],
        },
    ]
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    class FakeClient:
        def __init__(self):
            self.health_calls = 0
            self.query_calls = 0

        def health(self):
            self.health_calls += 1
            return {
                "status": "ok",
                "backend": {
                    "loaded": True,
                    "device": "cpu",
                    "dtype": "float32",
                    "model_name": "mock-model",
                },
            }

        def query(self, payload):
            self.query_calls += 1
            if payload["question"] == "What is the API called?":
                return {
                    "answer": "The API is called DocumentRAG.",
                    "latency": 0.25,
                    "citations": [{"citation": "c1"}],
                    "chunks": [{"content": "DocumentRAG", "metadata": {"file": "paper-a.pdf"}}],
                    "sources": ["paper-a.pdf"],
                }
            return {
                "answer": "I cannot find this information in the uploaded documents.",
                "latency": 0.4,
                "citations": [],
                "chunks": [],
                "sources": [],
            }

    runner = ProductionBenchmarkRunner(
        BenchmarkConfig(
            dataset_path=dataset_path,
            base_url="http://localhost:9001",
            output_dir=output_dir,
            timeout_s=1.0,
            health_timeout_s=1.0,
            retries=2,
            retry_backoff_s=0.0,
            resume=False,
            request_prefix="testbench",
        ),
        client=FakeClient(),
    )

    summary = runner.run()

    assert summary["total_questions"] == 2
    assert summary["passed_questions"] == 1
    assert summary["failed_questions"] == 1
    assert Path(output_dir, "summary.json").exists()
    assert Path(output_dir, "summary.md").exists()
    assert Path(output_dir, "per_question.jsonl").exists()
    assert Path(output_dir, "failures.jsonl").exists()
    assert Path(output_dir, "latency.csv").exists()

    per_question = Path(output_dir, "per_question.jsonl").read_text(encoding="utf-8").strip().splitlines()
    failures = Path(output_dir, "failures.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(per_question) == 2
    assert len(failures) == 1

    resume_client = FakeClient()
    resume_runner = ProductionBenchmarkRunner(
        BenchmarkConfig(
            dataset_path=dataset_path,
            base_url="http://localhost:9001",
            output_dir=output_dir,
            timeout_s=1.0,
            health_timeout_s=1.0,
            retries=2,
            retry_backoff_s=0.0,
            resume=True,
            request_prefix="testbench",
        ),
        client=resume_client,
    )

    resume_summary = resume_runner.run()
    assert resume_summary["total_questions"] == 2
    assert resume_client.query_calls == 0


def test_aggregate_records_computes_metrics():
    records = [
        {
            "status": "PASS",
            "http_latency_s": 0.25,
            "backend_latency_s": 0.20,
            "metrics": {"exact_match": True, "verdict": "Correct"},
        },
        {
            "status": "FAIL",
            "http_latency_s": 0.50,
            "backend_latency_s": 0.45,
            "metrics": {"exact_match": False, "verdict": "Incorrect"},
        },
    ]

    summary = aggregate_records(records)
    assert summary["total_questions"] == 2
    assert summary["passed_questions"] == 1
    assert summary["failed_questions"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["exact_match_rate"] == 0.5
    assert summary["avg_http_latency_s"] > 0
