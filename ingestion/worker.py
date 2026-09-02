"""
DocumentRAG Ingestion Worker.
Adapted from CodeGraphRAG background_ingest_repository — preserves all
infrastructure (progress tracking, snapshot/resume, batching, registry,
embedding cache, logging) while replacing code-specific logic with
PDF parsing and document chunking.

Performance changes vs original:
  - PDF parsing is parallelised via ThreadPoolExecutor (PARSE_WORKERS threads).
  - A module-level parsed-text cache (_PARSED_CACHE) avoids re-opening the same
    PDF within one process (useful on resume/retry scenarios).
  - Per-stage wall-clock timings are logged with throughput (items/s).
  - A single failed PDF never stops the entire run; it is skipped with a warning
    and counted in progress.failed_files.
  - Worker count is read from config.yaml workers.parse_workers (default: 4).

Preserved:
  - ProgressRegistry & IndexingProgressTracker
  - SnapshotManager (resume interrupted indexing)
  - File diff engine (incremental updates)
  - VectorStoreManager with batched embedding
  - MetadataStoreManager
  - RepositoryRegistry status transitions
  - Logging (logs/indexing.log)
  - Heartbeat updates during heavy CPU work
"""

import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import logging
import threading
import yaml

try:
    from eval.production_validation._stage_profiler import StageProfiler
except Exception:
    StageProfiler = None

logger = logging.getLogger(__name__)

from storage.registry import RepositoryRegistry, RepoStatus
from storage.vector_store import VectorStoreManager
from storage.metadata_store import MetadataStoreManager
from storage.snapshot import SnapshotManager
from ingestion.diff_engine import compute_file_diff

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)

# PDF extensions to index
_PDF_EXTENSIONS = {".pdf"}

# ---------------------------------------------------------------------------
# Module-level parsed-text cache
# Keyed by absolute PDF path. Prevents re-parsing the same file twice
# within the same process (e.g. after a partial resume).
# Thread-safe: protected by _PARSE_CACHE_LOCK.
# ---------------------------------------------------------------------------
_PARSED_CACHE: dict = {}
_PARSE_CACHE_LOCK = threading.Lock()


def _load_indexing_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("indexing", {})


def _load_worker_config() -> dict:
    """Load workers block from config.yaml, with safe defaults."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        full = yaml.safe_load(f) or {}
    return full.get("workers", {})


def _batch_chunks(chunks: list, batch_size: int):
    for index in range(0, len(chunks), batch_size):
        yield chunks[index: index + batch_size]


_UPSERT_MAX_RETRIES = 3
_UPSERT_RETRY_BACKOFF_SECONDS = 1.0


def _upsert_batch_with_retry(v_manager, batch: list, repo_id: str) -> bool:
    """
    Embed + upsert one batch, retrying transient failures a bounded number of
    times. Returns True if the batch was accepted, False if all attempts
    failed (the caller is responsible for recording the batch's chunk hashes
    as failed and continuing with the rest of the run rather than aborting).
    """
    import time

    for attempt in range(1, _UPSERT_MAX_RETRIES + 1):
        try:
            v_manager.add_chunks(batch)
            return True
        except Exception as e:
            logger.warning(
                f"[Worker] Upsert batch failed for repo={repo_id} "
                f"(attempt {attempt}/{_UPSERT_MAX_RETRIES}, {len(batch)} chunks): {e}"
            )
            if attempt < _UPSERT_MAX_RETRIES:
                time.sleep(_UPSERT_RETRY_BACKOFF_SECONDS * attempt)
    return False


def log_indexing_stage(
    repo_id: str,
    stage: str,
    event: str,
    duration: float = None,
    items: int = None,
    throughput: float = None,
):
    os.makedirs("logs", exist_ok=True)
    with open("logs/indexing.log", "a", encoding="utf-8") as f:
        msg = f"[{repo_id}] {stage} - {event}"
        if duration is not None:
            msg += f" | Duration: {duration:.2f}s"
        if items is not None:
            msg += f" | Items: {items}"
        if throughput is not None:
            msg += f" | Throughput: {throughput:.2f}/s"
        f.write(f"{datetime.now(timezone.utc).isoformat()} | {msg}\n")


def _is_pdf_file(file_path: str) -> bool:
    """Return True if the file path has a PDF extension."""
    _, ext = os.path.splitext(file_path.lower())
    return ext in _PDF_EXTENSIONS


def _resolve_target_path(target_path: str) -> list[str]:
    """
    Resolve target path across platforms and fallback to papers/<Category>
    if directory is empty or path does not exist.
    """
    candidates = [p.strip() for p in target_path.split(";") if p.strip()]
    resolved_paths = []

    for path in candidates:
        actual_path = path
        if not os.path.exists(actual_path):
            norm = path.replace("\\", "/")
            if len(norm) > 2 and norm[1] == ":":
                norm = norm[2:].lstrip("/")

            parts = [p for p in norm.split("/") if p]
            for known in ["demo_dataset", "papers", "repositories"]:
                if known in parts:
                    idx = parts.index(known)
                    sub = os.path.join(*parts[idx:])
                    if os.path.exists(sub):
                        actual_path = sub
                        break
            if not os.path.exists(actual_path):
                for i in range(len(parts)):
                    sub = os.path.join(*parts[i:])
                    if sub and os.path.exists(sub):
                        actual_path = sub
                        break

        # Check if actual_path contains any PDF files
        has_pdfs = False
        if os.path.exists(actual_path):
            if os.path.isfile(actual_path) and _is_pdf_file(actual_path):
                has_pdfs = True
            else:
                for root, dirs, files in os.walk(actual_path):
                    if any(_is_pdf_file(f) for f in files):
                        has_pdfs = True
                        break

        if not has_pdfs:
            lower_path = actual_path.lower()
            fallback_map = [
                (["retrieval", "rag"], "papers/RAG"),
                (["computer", "vision"], "papers/ComputerVision"),
                (["language", "nlp", "llm"], "papers/LLM"),
                (["medical"], "papers/MedicalAI"),
                (["graph"], "papers/GraphML"),
                (["robot"], "papers/Robotics"),
                (["artificial", "ai", "machine", "learning"], "papers/AI"),
            ]
            matched_fallback = None
            for kw_list, target_dir in fallback_map:
                if any(kw in lower_path for kw in kw_list):
                    if os.path.exists(target_dir):
                        matched_fallback = target_dir
                        break

            if matched_fallback:
                actual_path = matched_fallback
            elif os.path.exists("papers/AI"):
                actual_path = "papers/AI"

        resolved_paths.append(actual_path)

    return resolved_paths


def _discover_pdf_files(target_path: str) -> dict:
    """
    Walk the target directory (or semicolon-separated directories) and return:
        { relative_file_path: absolute_file_path }
    for all PDF files.
    """
    pdf_files = {}
    paths = _resolve_target_path(target_path)
    for path in paths:
        if not os.path.exists(path):
            continue
        if os.path.isfile(path):
            if _is_pdf_file(path):
                pdf_files[os.path.basename(path)] = path
            continue

        base_name = os.path.basename(os.path.normpath(path))
        for root, dirs, files in os.walk(path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not _is_pdf_file(fname):
                    continue
                full_path = os.path.join(root, fname)
                sub_rel = os.path.relpath(full_path, path).replace("\\", "/")
                rel_path = f"{base_name}/{sub_rel}" if len(paths) > 1 else sub_rel
                pdf_files[rel_path] = full_path
    return pdf_files


def _parse_and_chunk_pdf(
    abs_path: str,
    rel_path: str,
    collection_id: str,
) -> list:
    """
    Parse a single PDF and produce document chunks.

    Results are memoised in _PARSED_CACHE (keyed by abs_path) so that
    if the same PDF is encountered again in the same process the expensive
    parsing step is skipped.

    Returns list of chunk dicts or [] on parse failure.
    """
    from ingestion.pdf_parser import parse_pdf, get_sections_with_pages
    from ingestion.doc_chunker import chunk_document

    # --- Cache check ---
    with _PARSE_CACHE_LOCK:
        if abs_path in _PARSED_CACHE:
            cached_parsed = _PARSED_CACHE[abs_path]
        else:
            cached_parsed = None

    if cached_parsed is None:
        try:
            cached_parsed = parse_pdf(
                abs_path,
                filename_hint=os.path.splitext(os.path.basename(rel_path))[0],
            )
            with _PARSE_CACHE_LOCK:
                _PARSED_CACHE[abs_path] = cached_parsed
        except Exception as e:
            logger.warning(f"[Worker] Failed to parse {rel_path}: {e}")
            return []

    try:
        sections = get_sections_with_pages(cached_parsed)
        chunks = chunk_document(
            file_path=rel_path,
            sections=sections,
            paper_title=cached_parsed.get("title", ""),
            authors=cached_parsed.get("authors", ""),
            year=cached_parsed.get("year", ""),
            collection_id=collection_id,
        )
        return chunks
    except Exception as e:
        logger.warning(f"[Worker] Failed to chunk {rel_path}: {e}")
        return []


def background_ingest_repository(
    repo_id: str, source_path: str, registry: RepositoryRegistry
):
    """
    Background task: index a folder of PDF research papers into a Qdrant collection.

    Stages:
        discovering       → find all PDF files and compute diff vs snapshot
        parsing           → parse PDFs in parallel and produce chunks
        metadata_generation → persist metadata
        indexing_tier1 / indexing_tier2 → embed and upsert to Qdrant
        completed         → mark READY
    """
    from storage.progress import ProgressRegistry
    import time

    # Read worker config
    worker_cfg = _load_worker_config()
    parse_workers = max(1, worker_cfg.get("parse_workers", 4))

    progress = ProgressRegistry.get_tracker(repo_id)
    progress.update(
        status=RepoStatus.INDEXING,
        stage="discovering",
        percentage=0.0,
        files_processed=0,
        files_total=0,
        chunks_processed=0,
        chunks_total=0,
        embeddings_completed=0,
        embedding_rate=0.0,
        eta_seconds=-1.0,
        parse_workers=parse_workers,
        failed_files=0,
        retried_files=0,
        current_file="",
    )

    try:
        repo = registry.get_repository(repo_id)
        if not repo:
            progress.update(status=RepoStatus.FAILED, stage="failed")
            return

        log_indexing_stage(repo_id, "overall", "START")

        # ----------------------------------------------------------------
        # Stage profiler (optional — for benchmarking)
        # ----------------------------------------------------------------
        profiler = None
        if StageProfiler:
            stage_csv = os.environ.get("TTFUA_STAGE_TIMINGS_CSV")
            if stage_csv:
                profiler = StageProfiler(
                    os.environ.get("TTFUA_RUN_ID", "unknown"), repo.name, stage_csv
                )

        def measure(stage_name, func):
            if profiler:
                return profiler.measure(stage_name, func)
            return func()

        # ----------------------------------------------------------------
        # Tier 0: enter INDEXING_TIER0 early so UI can display status
        # ----------------------------------------------------------------
        registry.update_status(repo_id, RepoStatus.INDEXING_TIER0)
        progress.update(status=RepoStatus.INDEXING_TIER0)
        time.sleep(0.1)

        # Handle zip extraction
        target_path = source_path
        if source_path.endswith(".zip"):
            extract_dir = f"./repositories/{repo_id}"

            def _extract():
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(source_path, "r") as zf:
                    zf.extractall(extract_dir)
                return extract_dir

            target_path = measure("Repository extraction", _extract)

        # ----------------------------------------------------------------
        # 1. Discover PDF files
        # ----------------------------------------------------------------
        t_start = time.time()
        log_indexing_stage(repo_id, "discovery", "START")

        snapshot_manager = SnapshotManager()
        snapshot = measure("Snapshot load", lambda: snapshot_manager.get_snapshot(repo_id))

        # compute_file_diff works on file hashes — file-extension agnostic
        resolved_paths = _resolve_target_path(target_path)
        resolved_target = ";".join(resolved_paths)
        
        added_files, modified_files, deleted_files, new_file_hashes = measure(
            "Repository discovery",
            lambda: compute_file_diff(resolved_target, snapshot),
        )

        # Filter to PDFs only
        all_pdf_files = _discover_pdf_files(resolved_target)

        def _is_pdf_rel(rel_path: str) -> bool:
            return _is_pdf_file(rel_path)

        added_files = [f for f in added_files if _is_pdf_rel(f)]
        modified_files = [f for f in modified_files if _is_pdf_rel(f)]
        deleted_files = [f for f in deleted_files if _is_pdf_rel(f)]

        # Qdrant zero-point guard: if Qdrant collection is currently empty, force full re-indexing of all PDFs
        repo = registry.get_repository(repo_id)
        coll_name = repo.vector_collection if (repo and repo.vector_collection) else f"collection_{repo_id}"
        try:
            from storage.vector_store import VectorStoreManager
            vm = VectorStoreManager(collection_name=coll_name)
            if vm.count() == 0 and all_pdf_files:
                added_files = list(all_pdf_files.keys())
                modified_files = []
                deleted_files = []
        except Exception:
            if all_pdf_files:
                added_files = list(all_pdf_files.keys())

        # Resume fix: find PDF files whose chunks were not fully embedded
        missing_files = set()
        if snapshot.chunk_hashes and not (added_files and len(added_files) == len(all_pdf_files)):
            for file_path, hashes in snapshot.chunk_hashes.items():
                if not _is_pdf_rel(file_path):
                    continue
                if file_path in deleted_files:
                    continue
                embedded = set(snapshot.embedded_chunk_hashes.get(file_path, []))
                if any(h not in embedded for h in hashes):
                    missing_files.add(file_path)

        for file_path in missing_files:
            if file_path not in added_files and file_path not in modified_files:
                modified_files.append(file_path)

        duration = time.time() - t_start
        n_discovered = len(added_files) + len(modified_files) + len(deleted_files)
        log_indexing_stage(
            repo_id, "discovery", "END",
            duration=duration, items=n_discovered,
        )

        files_to_parse = set(added_files + modified_files)
        progress.update(
            stage="parsing",
            files_total=len(files_to_parse),
            files_processed=0,
        )

        # ----------------------------------------------------------------
        # 2. Parse PDF files — PARALLEL via ThreadPoolExecutor
        # ----------------------------------------------------------------
        t_start = time.time()
        log_indexing_stage(repo_id, "parsing", "START", items=len(files_to_parse))

        new_chunks_by_file: dict = {}
        failed_parse_count = 0

        if files_to_parse:
            sorted_files = sorted(files_to_parse)
            completed_count = 0
            completed_lock = threading.Lock()

            def _parse_one(rel_path: str):
                """Worker: parse one PDF and return (rel_path, chunks)."""
                abs_path = all_pdf_files.get(rel_path)
                if not abs_path or not os.path.exists(abs_path):
                    bname = os.path.basename(rel_path)
                    for k, v in all_pdf_files.items():
                        if k == bname or os.path.basename(k) == bname:
                            abs_path = v
                            break

                if not abs_path or not os.path.exists(abs_path):
                    if os.path.exists(rel_path):
                        abs_path = rel_path

                if not abs_path or not os.path.exists(abs_path):
                    logger.warning(f"[Worker] PDF not found on disk: {rel_path}")
                    return rel_path, []

                progress.update(current_file=os.path.basename(rel_path))
                chunks = _parse_and_chunk_pdf(abs_path, rel_path, repo_id)
                return rel_path, chunks

            with ThreadPoolExecutor(max_workers=parse_workers) as executor:
                future_to_path = {
                    executor.submit(_parse_one, rel): rel
                    for rel in sorted_files
                }
                for future in as_completed(future_to_path):
                    try:
                        rel_path, chunks = future.result()
                        new_chunks_by_file[rel_path] = chunks
                        if not chunks:
                            failed_parse_count += 1
                    except Exception as e:
                        rel_path = future_to_path[future]
                        logger.warning(f"[Worker] Unhandled parse error for {rel_path}: {e}")
                        new_chunks_by_file[rel_path] = []
                        failed_parse_count += 1

                    with completed_lock:
                        completed_count += 1
                    progress.update(
                        files_processed=completed_count,
                        failed_files=failed_parse_count,
                    )

        duration = time.time() - t_start
        total_new_chunks = sum(len(v) for v in new_chunks_by_file.values())
        throughput = len(files_to_parse) / max(0.01, duration)
        log_indexing_stage(
            repo_id, "parsing", "END",
            duration=duration,
            items=total_new_chunks,
            throughput=throughput,
        )
        logger.info(
            f"[Worker] Parsed {len(files_to_parse)} PDFs in {duration:.1f}s "
            f"({throughput:.2f} PDFs/s, {parse_workers} workers, "
            f"{failed_parse_count} failed)"
        )

        # Clear current file display
        progress.update(current_file="")

        # ----------------------------------------------------------------
        # 3. Compute chunk diff (add / delete)
        # ----------------------------------------------------------------
        chunks_to_add = []
        chunks_hashes_to_delete = []
        new_chunk_hashes = snapshot.chunk_hashes.copy()

        for file_path in deleted_files:
            old_hashes = new_chunk_hashes.pop(file_path, [])
            chunks_hashes_to_delete.extend(old_hashes)

        for file_path in added_files:
            chunks = new_chunks_by_file.get(file_path, [])
            hashes = [c["metadata"]["hash"] for c in chunks]
            chunks_to_add.extend(chunks)
            new_chunk_hashes[file_path] = hashes

        for file_path in modified_files:
            old_hashes = set(new_chunk_hashes.get(file_path, []))
            embedded_hashes = set(snapshot.embedded_chunk_hashes.get(file_path, []))
            chunks = new_chunks_by_file.get(file_path, [])
            new_hashes_list = []

            for c in chunks:
                chash = c["metadata"]["hash"]
                new_hashes_list.append(chash)
                if chash not in old_hashes or chash not in embedded_hashes:
                    chunks_to_add.append(c)

            for old_hash in old_hashes:
                if old_hash not in set(new_hashes_list):
                    chunks_hashes_to_delete.append(old_hash)

            new_chunk_hashes[file_path] = new_hashes_list

        # Early exit if nothing changed
        if not chunks_to_add and not chunks_hashes_to_delete and not deleted_files:
            repo.status = RepoStatus.READY
            repo.indexed_at = datetime.now(timezone.utc)
            registry.register(repo)
            progress.update(status=RepoStatus.READY, stage="completed", percentage=100.0)
            log_indexing_stage(repo_id, "overall", "END", duration=0.0)
            return

        # ----------------------------------------------------------------
        # 4. Persist metadata (Tier 0 — queryable before full embedding)
        # ----------------------------------------------------------------
        t_start = time.time()
        progress.update(stage="metadata_generation")
        log_indexing_stage(repo_id, "metadata_generation", "START")

        os.makedirs("metadata_storage", exist_ok=True)
        meta_manager = MetadataStoreManager(
            f"metadata_storage/{repo.metadata}.json"
        )
        if chunks_hashes_to_delete:
            measure(
                "Metadata deletion",
                lambda: meta_manager.remove_metadata(chunks_hashes_to_delete),
            )
        measure(
            "Metadata generation",
            lambda: meta_manager.add_metadata_batch(
                {c["metadata"]["hash"]: c["metadata"] for c in chunks_to_add}
            ),
        )

        duration = time.time() - t_start
        log_indexing_stage(
            repo_id, "metadata_generation", "END",
            duration=duration, items=len(chunks_to_add),
        )

        # Save snapshot before embedding (for resume)
        setattr(snapshot, "file_hashes", new_file_hashes)
        setattr(snapshot, "chunk_hashes", new_chunk_hashes)
        snapshot_manager.save_snapshot(repo_id, snapshot)

        # ----------------------------------------------------------------
        # 5. Initialize vector store and find already-embedded chunks
        # ----------------------------------------------------------------
        v_manager = VectorStoreManager(collection_name=repo.vector_collection)

        embedded_hashes_set = set()
        for hashes in snapshot.embedded_chunk_hashes.values():
            embedded_hashes_set.update(hashes)

        try:
            existing_chunks = v_manager.get_all_chunks()
            qdrant_hashes = {c["metadata"]["hash"] for c in existing_chunks}
            embedded_hashes_set.update(qdrant_hashes)
        except Exception as e:
            logger.warning(f"[Worker] Could not verify Qdrant state: {e}")

        chunks_needed = [
            c for c in chunks_to_add
            if c["metadata"]["hash"] not in embedded_hashes_set
        ]
        already_embedded_count = len(chunks_to_add) - len(chunks_needed)

        progress.update(
            chunks_total=len(chunks_to_add),
            embeddings_completed=already_embedded_count,
            chunks_processed=already_embedded_count,
            embedding_start_time=time.time(),
        )

        # ----------------------------------------------------------------
        # Tier 1: embed and index all needed chunks
        # ----------------------------------------------------------------
        registry.update_status(repo_id, RepoStatus.INDEXING_TIER1)
        progress.update(status=RepoStatus.INDEXING_TIER1, stage="indexing_tier1")
        t_start = time.time()
        log_indexing_stage(
            repo_id, "indexing_tier1", "START", items=len(chunks_needed)
        )

        if chunks_hashes_to_delete:
            measure(
                "Delete obsolete chunks",
                lambda: v_manager.delete_chunks(chunks_hashes_to_delete),
            )

        embedded_hashes = snapshot.embedded_chunk_hashes.copy()
        for file_path in deleted_files:
            embedded_hashes.pop(file_path, None)
        for file_path in modified_files:
            embedded_hashes.pop(file_path, None)

        indexing_config = _load_indexing_config()
        batch_size = indexing_config.get("background_batch_size", 64)
        current_completed = already_embedded_count
        upload_attempts = 0
        upload_failures = 0
        failed_chunk_hashes: list[str] = []

        for idx, batch in enumerate(_batch_chunks(chunks_needed, batch_size)):
            upload_attempts += len(batch)
            ok = _upsert_batch_with_retry(v_manager, batch, repo_id)
            if not ok:
                upload_failures += len(batch)
                failed_chunk_hashes.extend(c["metadata"]["hash"] for c in batch)
                # Skip marking this batch as embedded — reconciliation below
                # will detect the gap and the next indexing run will retry it
                # (its chunk hashes are still absent from embedded_hashes).
                continue

            batch_hashes = {c["metadata"]["hash"] for c in batch}
            for file_path, file_chunks in new_chunks_by_file.items():
                file_embedded = embedded_hashes.setdefault(file_path, [])
                file_embedded.extend(
                    c["metadata"]["hash"]
                    for c in file_chunks
                    if c["metadata"]["hash"] in batch_hashes
                    and c["metadata"]["hash"] not in file_embedded
                )
            current_completed += len(batch)
            repo.tier2_indexed_chunks = current_completed
            registry.register(repo)
            progress.update(
                embeddings_completed=current_completed,
                chunks_processed=current_completed,
            )
            setattr(snapshot, "embedded_chunk_hashes", embedded_hashes)
            snapshot_manager.save_snapshot(repo_id, snapshot)

        duration = time.time() - t_start
        throughput = len(chunks_needed) / max(0.1, duration)
        log_indexing_stage(
            repo_id, "indexing_tier1", "END",
            duration=duration, items=len(chunks_needed), throughput=throughput,
        )
        if upload_failures:
            logger.warning(
                f"[Worker] {upload_failures}/{upload_attempts} chunk upserts "
                f"failed after retries for repo={repo_id}"
            )

        # ----------------------------------------------------------------
        # Reconciliation: verify every chunk this run intended to have
        # indexed is actually present in Qdrant. A successful client call
        # does not by itself prove the data landed (see add_chunks retry
        # above) — check the real collection state before declaring victory.
        # ----------------------------------------------------------------
        expected_hashes = sorted({c["metadata"]["hash"] for c in chunks_to_add})
        verified_count, missing_hashes = v_manager.verify_points_exist(expected_hashes)

        if missing_hashes:
            # One bounded recovery pass: re-upsert exactly the missing chunks.
            hash_to_chunk = {c["metadata"]["hash"]: c for c in chunks_to_add}
            retry_batch = [hash_to_chunk[h] for h in missing_hashes if h in hash_to_chunk]
            if retry_batch:
                logger.warning(
                    f"[Worker] Reconciliation found {len(missing_hashes)} missing "
                    f"points for repo={repo_id}; attempting one recovery pass."
                )
                _upsert_batch_with_retry(v_manager, retry_batch, repo_id)
                verified_count, missing_hashes = v_manager.verify_points_exist(expected_hashes)

        reconciliation_passed = not missing_hashes

        # ----------------------------------------------------------------
        # Tier 2: finalize
        # ----------------------------------------------------------------
        registry.update_status(repo_id, RepoStatus.INDEXING_TIER2)
        progress.update(status=RepoStatus.INDEXING_TIER2, stage="indexing_tier2")

        # Save final snapshot
        measure(
            "Snapshot finalize",
            lambda: snapshot_manager.save_snapshot(repo_id, snapshot),
        )

        final_points = 0
        try:
            final_points = v_manager.count()
        except Exception:
            pass

        documents_parsed_ok = len(files_to_parse) - failed_parse_count

        print("=" * 80, flush=True)
        print(f"[INDEXING REPORT] Repository '{repo_id}'", flush=True)
        print(f"  Source Path : {target_path} -> Resolved: {resolved_target}", flush=True)
        print("  Documents:", flush=True)
        print(f"    discovered : {len(all_pdf_files)}", flush=True)
        print(f"    parsed     : {documents_parsed_ok}", flush=True)
        print(f"    failed     : {failed_parse_count}", flush=True)
        print("  Chunks:", flush=True)
        print(f"    generated  : {total_new_chunks}", flush=True)
        print(f"    prepared for this run : {len(chunks_to_add)}", flush=True)
        print(f"    embedded   : {current_completed - already_embedded_count} new ({already_embedded_count} already cached)", flush=True)
        print("  Qdrant:", flush=True)
        print(f"    unique points expected : {len(expected_hashes)}", flush=True)
        print(f"    upload attempts        : {upload_attempts}", flush=True)
        print(f"    upload failures        : {upload_failures}", flush=True)
        print(f"    points verified        : {verified_count}", flush=True)
        print(f"    collection point count : {final_points}", flush=True)
        print("  Reconciliation:", flush=True)
        if reconciliation_passed:
            print("    PASS", flush=True)
        else:
            print(f"    RECONCILIATION FAILED — {len(missing_hashes)} expected point(s) not found in Qdrant", flush=True)
            print(f"    missing hashes (first 10): {missing_hashes[:10]}", flush=True)
        print("=" * 80, flush=True)

        if not reconciliation_passed:
            error_msg = (
                f"Reconciliation failed: {len(missing_hashes)}/{len(expected_hashes)} "
                f"expected chunks are missing from Qdrant after upload + one retry pass."
            )
            logger.error(f"[Worker] {error_msg}")
            repo.status = RepoStatus.FAILED
            repo.last_error = error_msg
            registry.register(repo)
            progress.update(status=RepoStatus.FAILED, stage="reconciliation_failed", percentage=0.0)
            log_indexing_stage(repo_id, "overall", f"FAILED | {error_msg}")
            return

        # Transition to READY only after reconciliation confirms the data
        # this run promised is actually present in Qdrant.
        repo.status = RepoStatus.READY
        repo.indexed_at = datetime.now(timezone.utc)
        repo.last_error = None
        registry.register(repo)

        # Invalidate content-aware router cache so next query uses fresh chunk embeddings
        try:
            from retrieval.repository_router import invalidate_router_cache
            invalidate_router_cache(repo_id)
        except Exception:
            pass

        progress.update(status=RepoStatus.READY, stage="completed", percentage=100.0)
        log_indexing_stage(
            repo_id, "overall", "END",
            duration=time.time() - progress.start_time,
        )

        if profiler:
            profiler.write_csv()

    except Exception as e:
        logger.error(
            f"[Worker] Background ingestion failed for {repo_id}: {str(e)}",
            exc_info=True,
        )
        try:
            repo = registry.get_repository(repo_id)
            if repo:
                repo.last_error = str(e)
                registry.register(repo)
        except Exception:
            pass
        registry.update_status(repo_id, RepoStatus.FAILED)
        progress.update(status=RepoStatus.FAILED, stage="failed", percentage=0.0)
        log_indexing_stage(repo_id, "overall", f"FAILED | Error: {str(e)}")
