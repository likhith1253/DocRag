"""
DocumentRAG Ingestion Worker.
Adapted from CodeGraphRAG background_ingest_repository — preserves all
infrastructure (progress tracking, snapshot/resume, batching, registry,
embedding cache, logging) while replacing code-specific logic with
PDF parsing and document chunking.

Removed:
  - Git commit tracking
  - Language detection
  - AST parsing / Knowledge Graph construction
  - Code priority-tier logic (controller/service/api heuristics)

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
from datetime import datetime, timezone
import logging
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


def _load_indexing_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f).get("indexing", {})


def _batch_chunks(chunks: list, batch_size: int):
    for index in range(0, len(chunks), batch_size):
        yield chunks[index: index + batch_size]


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


def _discover_pdf_files(target_path: str) -> dict:
    """
    Walk the target directory and return a dict:
        { relative_file_path: absolute_file_path }
    for all PDF files.
    """
    pdf_files = {}
    for root, dirs, files in os.walk(target_path):
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not _is_pdf_file(fname):
                continue
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, target_path).replace("\\", "/")
            pdf_files[rel_path] = full_path
    return pdf_files


def _parse_and_chunk_pdf(
    abs_path: str,
    rel_path: str,
    collection_id: str,
) -> list:
    """
    Parse a single PDF and produce document chunks.
    Returns list of chunk dicts or [] on parse failure.
    """
    from ingestion.pdf_parser import parse_pdf, get_sections_with_pages
    from ingestion.doc_chunker import chunk_document

    try:
        parsed = parse_pdf(abs_path, filename_hint=os.path.splitext(os.path.basename(rel_path))[0])
        sections = get_sections_with_pages(parsed)
        chunks = chunk_document(
            file_path=rel_path,
            sections=sections,
            paper_title=parsed.get("title", ""),
            authors=parsed.get("authors", ""),
            year=parsed.get("year", ""),
            collection_id=collection_id,
        )
        return chunks
    except Exception as e:
        logger.warning(f"[Worker] Failed to parse/chunk {rel_path}: {e}")
        return []


def background_ingest_repository(
    repo_id: str, source_path: str, registry: RepositoryRegistry
):
    """
    Background task: index a folder of PDF research papers into a Qdrant collection.

    Stages:
        discovering  → find all PDF files and compute diff vs snapshot
        parsing      → parse PDFs and produce chunks
        metadata_generation → persist metadata
        indexing_tier1 / indexing_tier2 → embed and upsert to Qdrant
        completed    → mark READY
    """
    from storage.progress import ProgressRegistry
    import time

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
        added_files, modified_files, deleted_files, new_file_hashes = measure(
            "Repository discovery",
            lambda: compute_file_diff(target_path, snapshot),
        )

        # Filter to PDFs only
        all_pdf_files = _discover_pdf_files(target_path)

        def _is_pdf_rel(rel_path: str) -> bool:
            return _is_pdf_file(rel_path)

        added_files = [f for f in added_files if _is_pdf_rel(f)]
        modified_files = [f for f in modified_files if _is_pdf_rel(f)]
        deleted_files = [f for f in deleted_files if _is_pdf_rel(f)]

        # Resume fix: find PDF files whose chunks were not fully embedded
        missing_files = set()
        if snapshot.chunk_hashes:
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
        log_indexing_stage(
            repo_id,
            "discovery",
            "END",
            duration=duration,
            items=len(added_files) + len(modified_files) + len(deleted_files),
        )

        files_to_parse = set(added_files + modified_files)
        progress.update(
            stage="parsing",
            files_total=len(files_to_parse),
            files_processed=0,
        )

        # ----------------------------------------------------------------
        # 2. Parse only changed PDF files
        # ----------------------------------------------------------------
        t_start = time.time()
        log_indexing_stage(repo_id, "parsing", "START", items=len(files_to_parse))

        new_chunks_by_file: dict = {}
        if files_to_parse:
            for idx, rel_path in enumerate(sorted(files_to_parse)):
                abs_path = all_pdf_files.get(rel_path)
                if not abs_path or not os.path.exists(abs_path):
                    logger.warning(f"[Worker] PDF not found on disk: {rel_path}")
                    progress.update(files_processed=idx + 1)
                    continue
                chunks = _parse_and_chunk_pdf(abs_path, rel_path, repo_id)
                new_chunks_by_file[rel_path] = chunks
                progress.update(files_processed=idx + 1)

        duration = time.time() - t_start
        total_new_chunks = sum(len(v) for v in new_chunks_by_file.values())
        log_indexing_stage(
            repo_id, "parsing", "END", duration=duration, items=total_new_chunks
        )

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
            repo_id, "metadata_generation", "END", duration=duration, items=len(chunks_to_add)
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

        for idx, batch in enumerate(_batch_chunks(chunks_needed, batch_size)):
            v_manager.add_chunks(batch)
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
            duration=duration, items=len(chunks_needed), throughput=throughput
        )

        # ----------------------------------------------------------------
        # Tier 2: finalize (no deferred batch in DocumentRAG — all done above)
        # ----------------------------------------------------------------
        registry.update_status(repo_id, RepoStatus.INDEXING_TIER2)
        progress.update(status=RepoStatus.INDEXING_TIER2, stage="indexing_tier2")

        # Save final snapshot
        measure(
            "Snapshot finalize",
            lambda: snapshot_manager.save_snapshot(repo_id, snapshot),
        )

        # Transition to READY
        repo.status = RepoStatus.READY
        repo.indexed_at = datetime.now(timezone.utc)
        repo.last_error = None
        registry.register(repo)

        progress.update(status=RepoStatus.READY, stage="completed", percentage=100.0)
        log_indexing_stage(
            repo_id, "overall", "END",
            duration=time.time() - progress.start_time
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
