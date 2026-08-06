from __future__ import annotations

import csv
import json
import os
import socket
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from eval.metrics import compute_metrics

CANNOT_FIND_RESPONSE = "I cannot find this information in the uploaded documents."


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


@dataclass
class BenchmarkItem:
    question_id: str
    question: str
    expected_answer: str
    repository: str = ""
    collection: str = ""
    paper: str = ""
    key_concepts: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkConfig:
    dataset_path: Path
    base_url: str = "http://localhost:9001"
    output_dir: Path = Path("benchmark_results")
    timeout_s: float = 300.0
    health_timeout_s: float = 60.0
    retries: int = 3
    retry_backoff_s: float = 1.0
    resume: bool = False
    limit: Optional[int] = None
    request_prefix: str = "prodbench"
    query_path: str = "/query"
    health_path: str = "/health"


class BenchmarkHTTPError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body or ""


class BenchmarkPreflightError(RuntimeError):
    """Raised when pre-flight verification or prerequisite checks fail."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class BenchmarkAPIClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 300.0,
        retries: int = 3,
        retry_backoff_s: float = 1.0,
        opener: Optional[Callable[..., Any]] = None,
        health_path: str = "/health",
        query_path: str = "/query",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = max(1, int(retries))
        self.retry_backoff_s = float(retry_backoff_s)
        self._opener = opener or urllib.request.urlopen
        self.health_path = health_path
        self.query_path = query_path

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
            try:
                with self._opener(req, timeout=self.timeout_s) as resp:
                    raw = resp.read()
                    text = raw.decode("utf-8", errors="replace")
                    if not text.strip():
                        return {}
                    return json.loads(text)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
                if exc.code >= 500 and attempt < self.retries:
                    last_error = exc
                    time.sleep(self.retry_backoff_s * attempt)
                    continue
                raise BenchmarkHTTPError(f"HTTP {exc.code} for {url}", status_code=exc.code, body=body) from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.retry_backoff_s * attempt)
                    continue
                raise BenchmarkHTTPError(f"Request failed for {url}: {exc}") from exc

        raise BenchmarkHTTPError(f"Request failed for {url}: {last_error}")

    def health(self) -> Dict[str, Any]:
        return self._request_json("GET", self.health_path)

    def query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request_json("POST", self.query_path, payload)


def load_dataset(path: Path) -> List[BenchmarkItem]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        if "items" in raw:
            items = raw["items"]
        elif "questions" in raw:
            items = raw["questions"]
        else:
            raise ValueError(f"Unsupported dataset structure in {path}")
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(f"Unsupported dataset type in {path}")

    normalized: List[BenchmarkItem] = []
    for idx, item in enumerate(items, start=1):
        question_id = str(
            item.get("Question_ID")
            or item.get("id")
            or item.get("question_id")
            or f"Q{idx}"
        )
        question = item.get("Question") or item.get("question") or ""
        expected_answer = (
            item.get("Expected_Answer")
            or item.get("expected_answer")
            or item.get("answer")
            or ""
        )
        repository = str(item.get("repo_id") or item.get("repository") or item.get("collection_id") or "")
        collection = str(item.get("collection_id") or repository or "")
        paper = str(item.get("Paper") or item.get("paper") or item.get("source_file") or "")
        key_concepts = item.get("key_concepts") or item.get("Key_Concepts") or []
        if not isinstance(key_concepts, list):
            key_concepts = [str(key_concepts)]

        filters = dict(item.get("filters") or {})
        if paper and "file" not in filters and "paper_title" not in filters:
            filters["file"] = paper

        normalized.append(
            BenchmarkItem(
                question_id=question_id,
                question=str(question),
                expected_answer=str(expected_answer),
                repository=repository,
                collection=collection,
                paper=paper,
                key_concepts=[str(k) for k in key_concepts],
                filters=filters,
            )
        )

    return normalized


def aggregate_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(records)
    passed = [r for r in records if r.get("status") == "PASS"]
    failed = [r for r in records if r.get("status") != "PASS"]
    latencies = [float(r.get("http_latency_s", 0.0)) for r in records if r.get("http_latency_s") is not None]
    backend_latencies = [float(r.get("backend_latency_s", 0.0)) for r in records if r.get("backend_latency_s") is not None]
    exact_matches = [1.0 if r.get("metrics", {}).get("exact_match") else 0.0 for r in records]
    verdicts = [r.get("metrics", {}).get("verdict", "") for r in records]

    def _safe_median(values: List[float]) -> float:
        return float(statistics.median(values)) if values else 0.0

    return {
        "total_questions": total,
        "passed_questions": len(passed),
        "failed_questions": len(failed),
        "accuracy": (len(passed) / total) if total else 0.0,
        "exact_match_rate": (sum(exact_matches) / total) if total else 0.0,
        "avg_http_latency_s": (sum(latencies) / len(latencies)) if latencies else 0.0,
        "median_http_latency_s": _safe_median(latencies),
        "p95_http_latency_s": sorted(latencies)[max(0, int(round(0.95 * (len(latencies) - 1))))] if latencies else 0.0,
        "avg_backend_latency_s": (sum(backend_latencies) / len(backend_latencies)) if backend_latencies else 0.0,
        "verdict_counts": {v: verdicts.count(v) for v in sorted(set(verdicts)) if v},
    }


class ProductionBenchmarkRunner:
    def __init__(
        self,
        config: BenchmarkConfig,
        client: Optional[Any] = None,
    ):
        self.config = config
        self.output_dir = config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or BenchmarkAPIClient(
            base_url=config.base_url,
            timeout_s=config.timeout_s,
            retries=config.retries,
            retry_backoff_s=config.retry_backoff_s,
            health_path=config.health_path,
            query_path=config.query_path,
        )
        self.dataset = load_dataset(config.dataset_path)
        if config.limit is not None:
            self.dataset = self.dataset[: int(config.limit)]
        self._records_by_id: Dict[str, Dict[str, Any]] = {}
        if self.config.resume:
            self._load_existing_records()
        else:
            self._clear_existing_records()

    @property
    def per_question_path(self) -> Path:
        return self.output_dir / "per_question.jsonl"

    @property
    def failures_path(self) -> Path:
        return self.output_dir / "failures.jsonl"

    @property
    def summary_json_path(self) -> Path:
        return self.output_dir / "summary.json"

    @property
    def summary_md_path(self) -> Path:
        return self.output_dir / "summary.md"

    @property
    def latency_csv_path(self) -> Path:
        return self.output_dir / "latency.csv"

    def _clear_existing_records(self) -> None:
        self._records_by_id = {}
        for p in [self.per_question_path, self.failures_path, self.summary_json_path, self.summary_md_path, self.latency_csv_path]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def _load_existing_records(self) -> None:
        if not self.config.resume or not self.per_question_path.exists():
            return
        with open(self.per_question_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                qid = rec.get("question_id")
                if qid:
                    self._records_by_id[str(qid)] = rec

    def _wait_for_backend(self) -> Dict[str, Any]:
        deadline = time.time() + max(1.0, float(self.config.health_timeout_s))
        last_error: Optional[str] = None
        while time.time() < deadline:
            try:
                health = self.client.health()
                if health.get("status") != "ok":
                    last_error = f"health status={health.get('status')!r}"
                    time.sleep(1.0)
                    continue
                backend = health.get("backend") or {}
                is_loaded = bool(backend.get("loaded") or backend.get("model_loaded"))
                if backend and not is_loaded:
                    last_error = "backend loaded=false"
                    time.sleep(1.0)
                    continue
                return health
            except Exception as exc:
                last_error = str(exc)
                time.sleep(1.0)
        raise BenchmarkHTTPError(f"Backend unavailable after health check retries: {last_error}")

    def _run_preflight_checks(self) -> Dict[str, Any]:
        """
        STEPS 1-4 & STEP 6 Pre-flight System Verification:
        - Inspect registry (STEP 1)
        - Verify READY repos have non-zero Qdrant points (STEP 2)
        - Trigger auto-indexing if missing vectors & report chunk counts (STEP 3, STEP 9)
        - Verify models, vector store, cross encoder, LLM backend, API healthy (STEP 4)
        - Print system banner before Question 1 (STEP 6)
        """
        print("=" * 80, flush=True)
        print("DocumentRAG Production System Pre-Flight Diagnostics", flush=True)
        print("=" * 80, flush=True)

        # STEP 4: API & Backend Health
        health = self._wait_for_backend()
        if health.get("status") != "ok":
            raise BenchmarkPreflightError(f"API health check failed: status={health.get('status')!r}")

        backend_info = dict(health.get("backend") or {})
        is_loaded = bool(backend_info.get("loaded") or backend_info.get("model_loaded"))
        if not is_loaded:
            raise BenchmarkPreflightError("LLM backend is not loaded in API health payload.")

        llm_backend_name = (
            backend_info.get("model_name")
            or backend_info.get("backend_class")
            or backend_info.get("backend_name")
            or "LocalPyTorchBackend"
        )
        device_str = str(backend_info.get("device") or "cpu").lower()
        gpu_name = backend_info.get("gpu_name") or "None / CPU"

        cuda_available = False
        try:
            import torch
            cuda_available = torch.cuda.is_available()
            if cuda_available and (not gpu_name or gpu_name == "None / CPU"):
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            pass

        # STEP 1: Inspect Registry
        ready_repos = []
        registry = None
        try:
            from storage.registry import RepositoryRegistry, RepoStatus
            registry = RepositoryRegistry()
            all_repos = registry.list_repositories()
            ready_repos = [r for r in all_repos if r.status == RepoStatus.READY]
        except Exception:
            ready_repos = []
            registry = None

        # STEP 2 & 3: Qdrant Vector Store & Collections Inspection
        collections_info: Dict[str, int] = {}
        total_chunks_auto_indexed = 0
        embedding_model_name = "all-MiniLM-L6-v2"
        vector_dimension = 384

        try:
            from storage.vector_store import VectorStoreManager
            temp_vm = VectorStoreManager()
            temp_vm.client.get_collections()
            embedding_model_name = getattr(temp_vm, "embedding_model_name", embedding_model_name)
            vector_dimension = getattr(temp_vm, "vector_size", vector_dimension)

            if ready_repos and registry is not None:
                for repo in ready_repos:
                    coll_name = repo.vector_collection
                    vm = VectorStoreManager(collection_name=coll_name)
                    pt_count = vm.count()

                    # STEP 2 & 3: Check for 0 vectors
                    if pt_count == 0:
                        print(
                            f"[PRE-FLIGHT] Repository '{repo.name}' ({repo.repo_id}) collection '{coll_name}' has 0 vectors. "
                            f"Automatically triggering indexing...",
                            flush=True,
                        )
                        source_path = repo.source_path or f"papers/{repo.name}"
                        if not os.path.exists(source_path) and os.path.exists("papers/AI"):
                            source_path = "papers/AI"

                        if not os.path.exists(source_path):
                            raise BenchmarkPreflightError(
                                f"Repository '{repo.name}' missing vectors, and source_path '{source_path}' does not exist."
                            )

                        try:
                            from storage.snapshot import SnapshotManager
                            SnapshotManager().delete_snapshot(repo.repo_id)
                        except Exception:
                            pass

                        from ingestion.worker import background_ingest_repository
                        count_before = pt_count
                        try:
                            background_ingest_repository(repo.repo_id, source_path, registry)
                        except Exception as ing_err:
                            raise BenchmarkPreflightError(
                                f"Auto-indexing genuinely failed for repository '{repo.name}': {ing_err}"
                            ) from ing_err

                        pt_count = vm.count()
                        chunks_inserted = pt_count - count_before
                        if pt_count == 0:
                            raise BenchmarkPreflightError(
                                f"Auto-indexing finished for repository '{repo.name}', but point count is still 0."
                            )

                        total_chunks_auto_indexed += chunks_inserted
                        # STEP 9: State inserted chunks
                        print(
                            f"[AUTO-INDEX] Repository '{repo.name}' ({repo.repo_id}) successfully indexed. "
                            f"Exactly {chunks_inserted} chunks were inserted. (Total collection points: {pt_count})",
                            flush=True,
                        )

                    collections_info[coll_name] = pt_count
            else:
                dataset_colls = sorted(list({item.collection for item in self.dataset if item.collection}))
                if not dataset_colls:
                    dataset_colls = ["chunks"]
                for c_name in dataset_colls:
                    vm = VectorStoreManager(collection_name=c_name)
                    collections_info[c_name] = vm.count()

        except BenchmarkPreflightError:
            raise
        except Exception as exc:
            if ready_repos:
                raise BenchmarkPreflightError(f"Vector store reachability check failed: {exc}") from exc
            else:
                collections_info["default"] = 0

        # STEP 4: Cross Encoder Check
        cross_encoder_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        try:
            from storage.vector_store import _get_config
            cfg = _get_config()
            cross_encoder_name = cfg.get("reranker_model", cross_encoder_name)
            from sentence_transformers import CrossEncoder
            from retrieval.cross_encoder_rerank import _cross_encoder_cache
            cache_key = f"{cross_encoder_name}::{device_str}"
            if cache_key not in _cross_encoder_cache:
                _cross_encoder_cache[cache_key] = CrossEncoder(cross_encoder_name, device=device_str)
        except Exception:
            pass

        # STEP 6: Print System Banner
        repo_count = len(ready_repos) if ready_repos else len(collections_info)
        coll_names_str = ", ".join(collections_info.keys())
        pt_counts_str = ", ".join(f"{k}: {v}" for k, v in collections_info.items())

        print(f"Repository count           : {repo_count}", flush=True)
        print(f"Collection names           : {coll_names_str}", flush=True)
        print(f"Point count per collection : {pt_counts_str}", flush=True)
        print(f"Embedding model            : {embedding_model_name}", flush=True)
        print(f"Vector dimension           : {vector_dimension}", flush=True)
        print(f"Cross encoder              : {cross_encoder_name}", flush=True)
        print(f"LLM backend                : {llm_backend_name}", flush=True)
        print(f"GPU                        : {gpu_name}", flush=True)
        print(f"CUDA                       : {cuda_available}", flush=True)
        print(f"Device                     : {device_str.upper()}", flush=True)
        print("=" * 80, flush=True)

        return {
            "backend_info": backend_info,
            "ready_repos": ready_repos,
            "collections_info": collections_info,
            "total_chunks_auto_indexed": total_chunks_auto_indexed,
            "embedding_model_name": embedding_model_name,
            "vector_dimension": vector_dimension,
            "cross_encoder_name": cross_encoder_name,
            "llm_backend_name": llm_backend_name,
            "gpu_name": gpu_name,
            "cuda_available": cuda_available,
            "device": device_str,
        }

    def _print_retrieval_diagnostics(
        self,
        item: BenchmarkItem,
        response: Dict[str, Any],
        http_status: int,
        http_latency_s: float,
        backend_latency_s: float,
        failure_reason: str,
        citations: List[Any],
        chunks: List[Any],
        actual_answer: str,
    ) -> None:
        """STEP 8: Print retrieval diagnostics immediately if retrieval fails."""
        print("-" * 80, flush=True)
        print(f"[RETRIEVAL DIAGNOSTICS FAILURE] {item.question_id}", flush=True)
        print(f"  Question          : {item.question}", flush=True)
        print(f"  Collection / Repo : {item.collection or item.repository or 'N/A'}", flush=True)
        print(f"  HTTP Status       : {http_status}", flush=True)
        print(f"  HTTP Latency      : {http_latency_s:.3f}s | Backend Latency: {backend_latency_s:.3f}s", flush=True)
        print(f"  Citations Count   : {len(citations)}", flush=True)
        print(f"  Chunks Count      : {len(chunks)}", flush=True)
        print(f"  Failure Reason    : {failure_reason}", flush=True)
        if actual_answer:
            print(f"  Actual Answer     : {actual_answer[:200]}...", flush=True)
        if response.get("error"):
            print(f"  API Error         : {response.get('error')}", flush=True)
        if chunks:
            top_chunk = chunks[0]
            score = top_chunk.get("score") or top_chunk.get("rerank_score") or 0.0
            snippet = str(top_chunk.get("content", ""))[:120].replace("\n", " ")
            print(f"  Top Chunk Score   : {score:.4f} | Snippet: {snippet}...", flush=True)
        print("-" * 80, flush=True)

    def _build_payload(self, item: BenchmarkItem, request_id: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "question": item.question,
            "request_id": request_id,
            "filters": item.filters or {},
        }
        if item.collection:
            payload["collection_id"] = item.collection
            payload["repo_id"] = item.collection
        elif item.repository:
            payload["collection_id"] = item.repository
            payload["repo_id"] = item.repository
        return payload

    def _score(self, expected: str, actual: str, key_concepts: List[str]) -> Dict[str, Any]:
        metrics = compute_metrics(expected, actual, key_concepts=key_concepts)
        metrics["accuracy"] = metrics.get("verdict") == "Correct"
        return metrics

    def _status_from_metrics(self, actual: str, metrics: Dict[str, Any]) -> str:
        if not actual.strip():
            return "FAIL"
        if actual.strip() == CANNOT_FIND_RESPONSE:
            return "FAIL"
        return "PASS" if metrics.get("verdict") == "Correct" else "FAIL"

    def _write_jsonl(self, path: Path, rows: Iterable[Dict[str, Any]]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    def _write_csv(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        fieldnames = [
            "question_id",
            "repository",
            "collection",
            "paper",
            "status",
            "verdict",
            "http_latency_s",
            "backend_latency_s",
            "citations_count",
            "sources_count",
            "exact_match",
            "semantic_similarity",
            "grounding_score_percent",
            "concept_coverage_percent",
            "failure_reason",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                metrics = row.get("metrics", {})
                writer.writerow(
                    {
                        "question_id": row.get("question_id"),
                        "repository": row.get("repository"),
                        "collection": row.get("collection"),
                        "paper": row.get("paper"),
                        "status": row.get("status"),
                        "verdict": metrics.get("verdict"),
                        "http_latency_s": row.get("http_latency_s"),
                        "backend_latency_s": row.get("backend_latency_s"),
                        "citations_count": row.get("citations_count"),
                        "sources_count": row.get("sources_count"),
                        "exact_match": metrics.get("exact_match"),
                        "semantic_similarity": metrics.get("semantic_similarity"),
                        "grounding_score_percent": metrics.get("grounding_score_percent"),
                        "concept_coverage_percent": metrics.get("concept_coverage_percent"),
                        "failure_reason": row.get("failure_reason", ""),
                    }
                )

    def _write_outputs(
        self,
        *,
        records: List[Dict[str, Any]],
        failures: List[Dict[str, Any]],
        backend_info: Dict[str, Any],
        started_at: str,
        finished_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        summary = aggregate_records(records)
        summary.update(
            {
                "dataset_path": str(self.config.dataset_path),
                "output_dir": str(self.output_dir),
                "base_url": self.config.base_url,
                "resume": self.config.resume,
                "limit": self.config.limit,
                "started_at": started_at,
                "finished_at": finished_at or _now_iso(),
                "backend": backend_info,
                "completed_questions": [r.get("question_id") for r in records if r.get("status") == "PASS"],
                "failed_question_ids": [r.get("question_id") for r in failures],
            }
        )

        self._write_jsonl(self.per_question_path, records)
        self._write_jsonl(self.failures_path, failures)
        self._write_csv(self.latency_csv_path, records)

        with open(self.summary_json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

        self.summary_md_path.write_text(self._render_summary_md(summary, records, failures), encoding="utf-8")
        return summary

    def _render_summary_md(self, summary: Dict[str, Any], records: List[Dict[str, Any]], failures: List[Dict[str, Any]]) -> str:
        backend = summary.get("backend") or {}
        lines = [
            "# Production API Benchmark Summary",
            "",
            f"- Dataset: `{summary.get('dataset_path')}`",
            f"- Base URL: `{summary.get('base_url')}`",
            f"- Output Dir: `{summary.get('output_dir')}`",
            f"- Started: `{summary.get('started_at')}`",
            f"- Finished: `{summary.get('finished_at')}`",
            f"- Backend Device: `{str(backend.get('device', 'unknown')).upper()}`" if backend.get("device") else "- Backend Device: `unknown`",
            f"- Backend Model: `{backend.get('model_name', 'unknown')}`",
            f"- Backend Loaded: `{backend.get('loaded', 'unknown')}`",
            "",
            "## Results",
            "",
            f"- Total Questions: {summary.get('total_questions', 0)}",
            f"- Passed: {summary.get('passed_questions', 0)}",
            f"- Failed: {summary.get('failed_questions', 0)}",
            f"- Accuracy: {summary.get('accuracy', 0.0):.4f}",
            f"- Exact Match Rate: {summary.get('exact_match_rate', 0.0):.4f}",
            f"- Avg HTTP Latency: {summary.get('avg_http_latency_s', 0.0):.2f}s",
            f"- Median HTTP Latency: {summary.get('median_http_latency_s', 0.0):.2f}s",
            f"- P95 HTTP Latency: {summary.get('p95_http_latency_s', 0.0):.2f}s",
            "",
            "## Failure Breakdown",
            "",
            f"- Failure Count: {len(failures)}",
            "",
        ]
        if failures:
            lines.extend([
                "| Question | Repository | Collection | Failure Reason |",
                "| --- | --- | --- | --- |",
            ])
            for rec in failures[:25]:
                lines.append(
                    f"| {rec.get('question_id')} | {rec.get('repository', '')} | {rec.get('collection', '')} | {rec.get('failure_reason', '')} |"
                )
        return "\n".join(lines) + "\n"

    def run(self) -> Dict[str, Any]:
        started_at = _now_iso()

        # STEPS 1-4 & STEP 6: Execute pre-flight verification and system banner print
        preflight = self._run_preflight_checks()
        backend_info = preflight["backend_info"]

        # STEP 7: Only after all checks succeed begin Question 1
        total = len(self.dataset)
        records = list(self._records_by_id.values())
        completed_ids = {str(r.get("question_id")) for r in records}

        print(f"Starting Question 1 / {total} (Resume: {self.config.resume})", flush=True)
        print("=" * 80, flush=True)

        try:
            for idx, item in enumerate(self.dataset, start=1):
                if item.question_id in completed_ids:
                    print(f"[{idx}/{total}] Skipping {item.question_id} (already completed)", flush=True)
                    continue

                request_id = f"{self.config.request_prefix}-{item.question_id.lower()}-{idx}"
                print(f"[{idx}/{total}] {item.question_id}: {item.question[:90]}", flush=True)
                started = time.perf_counter()
                http_status = 200
                response: Dict[str, Any] = {}
                error_text = ""

                try:
                    response = self.client.query(self._build_payload(item, request_id))
                    actual_answer = str(response.get("answer", ""))
                except BenchmarkHTTPError as exc:
                    http_status = exc.status_code or 0
                    error_text = str(exc)
                    response = {
                        "error": error_text,
                        "http_status": http_status,
                        "body": exc.body,
                    }
                    actual_answer = ""
                except Exception as exc:
                    http_status = 0
                    error_text = str(exc)
                    response = {"error": error_text}
                    actual_answer = ""

                http_latency_s = time.perf_counter() - started
                backend_latency_s = float(
                    response.get("latency", 0.0)
                    or response.get("latency_s", 0.0)
                    or 0.0
                )
                citations = response.get("citations", []) or []
                chunks = response.get("chunks", []) or []
                sources = response.get("sources", []) or []

                metrics = self._score(item.expected_answer, actual_answer, item.key_concepts)
                status = self._status_from_metrics(actual_answer, metrics)

                failure_reason = ""
                if status != "PASS":
                    if error_text:
                        failure_reason = error_text
                    elif actual_answer.strip() == CANNOT_FIND_RESPONSE:
                        failure_reason = "Grounding fallback returned"
                    elif not citations:
                        failure_reason = "No citations returned"
                    else:
                        failure_reason = f"Metric verdict: {metrics.get('verdict')}"

                    # STEP 8: Print retrieval diagnostics immediately on failure
                    self._print_retrieval_diagnostics(
                        item=item,
                        response=response,
                        http_status=http_status,
                        http_latency_s=http_latency_s,
                        backend_latency_s=backend_latency_s,
                        failure_reason=failure_reason,
                        citations=citations,
                        chunks=chunks,
                        actual_answer=actual_answer,
                    )

                record = {
                    "timestamp": _now_iso(),
                    "request_id": request_id,
                    "question_id": item.question_id,
                    "question": item.question,
                    "expected_answer": item.expected_answer,
                    "actual_answer": actual_answer,
                    "repository": item.repository,
                    "collection": item.collection,
                    "paper": item.paper,
                    "filters": item.filters,
                    "key_concepts": item.key_concepts,
                    "status": status,
                    "failure_reason": failure_reason,
                    "http_status": http_status,
                    "http_latency_s": round(http_latency_s, 4),
                    "backend_latency_s": round(backend_latency_s, 4),
                    "response": response,
                    "citations": citations,
                    "chunks": chunks,
                    "sources": sources,
                    "citations_count": len(citations),
                    "chunks_count": len(chunks),
                    "sources_count": len(sources),
                    "metrics": metrics,
                }

                self._records_by_id[item.question_id] = record
                records = [self._records_by_id[q.question_id] for q in self.dataset if q.question_id in self._records_by_id]
                failures = [r for r in records if r.get("status") != "PASS"]
                completed_ids.add(item.question_id)

                self._write_outputs(
                    records=records,
                    failures=failures,
                    backend_info=backend_info,
                    started_at=started_at,
                )

                print(
                    f"    status={status} latency={http_latency_s:.2f}s "
                    f"backend={backend_latency_s:.2f}s citations={len(citations)}",
                    flush=True,
                )

        except KeyboardInterrupt:
            print("\nInterrupted. Saving partial benchmark outputs...", flush=True)
        finally:
            records = [self._records_by_id[q.question_id] for q in self.dataset if q.question_id in self._records_by_id]
            failures = [r for r in records if r.get("status") != "PASS"]
            summary = self._write_outputs(
                records=records,
                failures=failures,
                backend_info=backend_info,
                started_at=started_at,
                finished_at=_now_iso(),
            )

        return summary


def build_runner_from_args(args: Any) -> ProductionBenchmarkRunner:
    resume = bool(getattr(args, "resume", False))
    if getattr(args, "no_resume", False):
        resume = False

    config = BenchmarkConfig(
        dataset_path=Path(args.dataset).expanduser().resolve(),
        base_url=args.base_url,
        output_dir=Path(args.output_dir).expanduser().resolve(),
        timeout_s=args.timeout,
        health_timeout_s=args.health_timeout,
        retries=args.retries,
        retry_backoff_s=args.retry_backoff,
        resume=resume,
        limit=args.limit,
        request_prefix=args.request_prefix,
        query_path=args.query_path,
        health_path=args.health_path,
    )
    return ProductionBenchmarkRunner(config=config)


def add_cli_args(parser: Any) -> None:
    parser.add_argument("--dataset", default="eval/generated_benchmark.json", help="Path to the benchmark dataset JSON.")
    parser.add_argument("--base-url", default="http://localhost:9001", help="Production API base URL.")
    parser.add_argument("--output-dir", default="benchmark_results", help="Directory for benchmark artifacts.")
    parser.add_argument("--timeout", type=float, default=300.0, help="HTTP request timeout in seconds.")
    parser.add_argument("--health-timeout", type=float, default=60.0, help="How long to wait for the backend health check.")
    parser.add_argument("--retries", type=int, default=3, help="Retry count for HTTP requests.")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="Backoff seconds between retries.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for local smoke runs.")
    parser.add_argument("--request-prefix", default="prodbench", help="Prefix for request IDs.")
    parser.add_argument("--query-path", default="/query", help="Query route path.")
    parser.add_argument("--health-path", default="/health", help="Health route path.")
    parser.add_argument("--resume", action="store_true", default=False, help="Explicitly enable resume mode to continue previous benchmark run.")
    parser.add_argument("--no-resume", action="store_true", help="Deprecated. Resume is disabled by default.")


def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Production API benchmark runner for DocumentRAG.")
    add_cli_args(parser)
    args = parser.parse_args(argv)

    try:
        runner = build_runner_from_args(args)
        summary = runner.run()
    except (BenchmarkHTTPError, BenchmarkPreflightError, FileNotFoundError) as exc:
        print(f"\n[BENCHMARK ABORTED] {exc}", flush=True)
        return 1

    print("\nBenchmark complete.", flush=True)
    print(f"Accuracy: {summary.get('accuracy', 0.0):.4f}", flush=True)
    print(f"Artifacts written to: {runner.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
