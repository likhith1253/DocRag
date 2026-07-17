"""
Document Chunker for DocumentRAG.
Produces section-aware, page-annotated chunks from parsed PDF research papers.

Key properties:
  - Respects section boundaries: never splits a paragraph across sections
  - Tracks page_start / page_end per chunk
  - Preserves overlap between consecutive chunks within a section
  - Uses the same hash-based dedup as the original CodeGraphRAG chunker
  - Metadata schema replaces code-specific fields with document fields
"""

import os
import re
import yaml
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_chunking_config() -> tuple:
    """
    Load chunking configuration from config.yaml.
    Returns (max_chunk_tokens, overlap_tokens).
    """
    max_chunk_tokens = 512
    overlap_tokens = 64
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            chunking = config.get("chunking", {})
            max_chunk_tokens = chunking.get("max_chunk_tokens", 512)
            overlap_tokens = chunking.get("overlap_tokens", 64)
        except Exception:
            pass
    return max_chunk_tokens, overlap_tokens


def _count_tokens(text: str) -> int:
    """Approximate token count — same algorithm as original chunker."""
    if not text:
        return 0
    return len(re.findall(r"\w+|[^\w\s]", text))


# ---------------------------------------------------------------------------
# Sliding window on lines (preserved from original chunker)
# ---------------------------------------------------------------------------

def _chunk_text_sliding_window(
    text: str, max_tokens: int, overlap_tokens: int
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks respecting token budget.
    Returns list of {"content": str, "relative_line_start": int}.
    """
    lines = text.splitlines()
    if not lines:
        return []

    line_token_counts = [_count_tokens(l) for l in lines]
    chunks = []
    n = len(lines)
    i = 0

    while i < n:
        current_lines = []
        current_tokens = 0
        j = i

        while j < n:
            t = line_token_counts[j]
            if current_tokens + t <= max_tokens or not current_lines:
                current_lines.append(lines[j])
                current_tokens += t
                j += 1
            else:
                break

        chunks.append({
            "content": "\n".join(current_lines),
            "relative_line_start": i
        })

        if j == n:
            break

        # Compute overlap backtrack
        overlap_collected = 0
        backtrack_idx = j - 1
        while (
            backtrack_idx >= i
            and overlap_collected + line_token_counts[backtrack_idx] <= overlap_tokens
        ):
            overlap_collected += line_token_counts[backtrack_idx]
            backtrack_idx -= 1

        next_i = backtrack_idx + 1
        if next_i <= i:
            next_i = i + 1
        i = next_i

    return chunks


# ---------------------------------------------------------------------------
# Document chunker
# ---------------------------------------------------------------------------

def chunk_document(
    file_path: str,
    sections: List[Dict[str, Any]],
    paper_title: str,
    authors: str,
    year: str,
    collection_id: str,
) -> List[Dict[str, Any]]:
    """
    Produce document chunks from a parsed paper's sections.

    Args:
        file_path: Relative path of the PDF file within the collection folder.
        sections: Output of pdf_parser.get_sections_with_pages().
        paper_title: Extracted or derived paper title.
        authors: Author string (may be empty).
        year: Publication year string (may be empty).
        collection_id: The repository/collection UUID for isolation.

    Returns:
        List of chunk dicts:
            {
                "content": str,
                "metadata": {
                    "collection_id": str,
                    "paper_title": str,
                    "authors": str,
                    "year": str,
                    "section": str,
                    "page_start": int,
                    "page_end": int,
                    "file": str,
                    "hash": str,
                    "timestamp": str,
                }
            }
    """
    max_chunk_tokens, overlap_tokens = _load_chunking_config()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    final_chunks = []

    for section in sections:
        heading = section.get("heading", "Body")
        page_start = section.get("page_start", 1)
        page_end = section.get("page_end", page_start)
        content = section.get("content", "").strip()

        if not content:
            continue

        # If entire section fits within token budget, emit as single chunk
        if _count_tokens(content) <= max_chunk_tokens:
            raw_chunks = [{"content": content, "relative_line_start": 0}]
        else:
            # Apply sliding window within section
            raw_chunks = _chunk_text_sliding_window(content, max_chunk_tokens, overlap_tokens)

        for rc in raw_chunks:
            chunk_content = rc["content"].strip()
            if not chunk_content:
                continue

            # Use exact page range using the line_pages map
            chunk_line_start = rc["relative_line_start"]
            chunk_line_end = chunk_line_start + len(chunk_content.splitlines()) - 1
            line_pages = section.get("line_pages", [])
            
            if line_pages and chunk_line_start < len(line_pages):
                chunk_page_start = line_pages[chunk_line_start]
                end_idx = min(chunk_line_end, len(line_pages) - 1)
                chunk_page_end = line_pages[end_idx]
            else:
                chunk_page_start = page_start
                chunk_page_end = page_end

            content_hash = hashlib.sha256(
                (chunk_content + file_path + collection_id).encode("utf-8")
            ).hexdigest()

            metadata = {
                "collection_id": collection_id,
                "paper_title": paper_title,
                "authors": authors,
                "year": year,
                "section": heading,
                "page_start": chunk_page_start,
                "page_end": chunk_page_end,
                "file": file_path,
                "hash": content_hash,
                "timestamp": timestamp,
            }

            final_chunks.append({
                "content": chunk_content,
                "metadata": metadata
            })

    return final_chunks
