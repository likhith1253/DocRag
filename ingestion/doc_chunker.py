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
# Structural boundary detection
# ---------------------------------------------------------------------------

def _is_variable_value_pair(line: str) -> bool:
    """
    Detect lines that are variable-value pairs (e.g., "gamma = 0.99").
    These should not be split from their context.
    """
    pattern = r'^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*[=:]\s*[\-\+]?[0-9]*\.?[0-9]+'
    return bool(re.match(pattern, line))

def _is_bullet_point(line: str) -> bool:
    """
    Detect bullet points that should stay together.
    """
    stripped = line.strip()
    return bool(re.match(r'^[\-\*\•\d+\.\)]\s', stripped))

def _is_equation_line(line: str) -> bool:
    """
    Detect lines that are part of equations.
    """
    patterns = [
        r'\\[a-zA-Z]+\{',  # LaTeX commands
        r'\$.*\$',  # Inline math
        r'^\s*[a-zA-Z_]\s*[=+\-*/]\s*[a-zA-Z0-9_]',  # Simple equations
        r'^\s*\(?\d+\)?\s*$',  # Equation numbers like (1) or 1
        r'(?i)equation\s*\(\d+\)', # Mentions like Equation (1)
        r'^\s*[∑∏∫]\s*', # Math symbols
    ]
    return any(re.search(p, line) for p in patterns)

def _is_table_row(line: str) -> bool:
    """
    Detect lines that are part of a table (Markdown or tab-separated).
    """
    stripped = line.strip()
    return '\t' in line or re.search(r'\s{3,}', line) or stripped.startswith('|')

def _find_structural_blocks(lines: List[str]) -> List[List[int]]:
    """Group line indices into indivisible blocks."""
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _is_table_row(line):
            block = [i]
            i += 1
            while i < n and _is_table_row(lines[i]):
                block.append(i)
                i += 1
            blocks.append(block)
        elif _is_equation_line(line):
            block = [i]
            i += 1
            while i < n and _is_equation_line(lines[i]):
                block.append(i)
                i += 1
            blocks.append(block)
        elif _is_variable_value_pair(line):
            block = [i]
            i += 1
            while i < n and _is_variable_value_pair(lines[i]):
                block.append(i)
                i += 1
            blocks.append(block)
        elif _is_bullet_point(line):
            block = [i]
            i += 1
            while i < n and _is_bullet_point(lines[i]):
                block.append(i)
                i += 1
            blocks.append(block)
        else:
            blocks.append([i])
            i += 1
    return blocks

def _detect_chunk_type(content: str) -> str:
    """
    Detect the type of content in a chunk.
    Returns: TEXT, TABLE, EQUATION, HYPERPARAMETERS, ALGORITHM, or MIXED
    """
    lines = content.splitlines()
    
    table_count = sum(1 for line in lines if _is_table_row(line))
    equation_count = sum(1 for line in lines if _is_equation_line(line))
    var_value_count = sum(1 for line in lines if _is_variable_value_pair(line))
    bullet_count = sum(1 for line in lines if _is_bullet_point(line))
    
    total_lines = len(lines)
    if total_lines == 0:
        return "TEXT"
        
    if table_count > total_lines * 0.4:
        return "TABLE"
    elif equation_count > total_lines * 0.3:
        return "EQUATION"
    elif var_value_count > total_lines * 0.2:
        return "HYPERPARAMETERS"
    elif bullet_count > total_lines * 0.4:
        return "ALGORITHM"
    elif table_count > 0 or equation_count > 0 or var_value_count > 0:
        return "MIXED"
    else:
        return "TEXT"


# ---------------------------------------------------------------------------
# Sliding window on lines (preserved from original chunker)
# ---------------------------------------------------------------------------

def _chunk_text_sliding_window(
    text: str, max_tokens: int, overlap_tokens: int, respect_boundaries: bool = True
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks respecting token budget and structural boundaries.
    Returns list of {"content": str, "relative_line_start": int}.
    """
    lines = text.splitlines()
    if not lines:
        return []

    line_token_counts = [_count_tokens(l) for l in lines]
    chunks = []
    
    if respect_boundaries:
        blocks = _find_structural_blocks(lines)
    else:
        blocks = [[i] for i in range(len(lines))]
        
    n_blocks = len(blocks)
    i = 0
    
    while i < n_blocks:
        current_lines = []
        current_tokens = 0
        j = i
        start_line_idx = blocks[i][0]
        
        while j < n_blocks:
            block = blocks[j]
            block_tokens = sum(line_token_counts[idx] for idx in block)
            
            if current_tokens + block_tokens <= max_tokens or not current_lines:
                for idx in block:
                    current_lines.append(lines[idx])
                current_tokens += block_tokens
                j += 1
            else:
                break
                
        chunks.append({
            "content": "\n".join(current_lines),
            "relative_line_start": start_line_idx
        })
        
        if j == n_blocks:
            break
            
        # Compute overlap backtrack block by block
        overlap_collected = 0
        backtrack_idx = j - 1
        while backtrack_idx > i:
            block = blocks[backtrack_idx]
            block_tokens = sum(line_token_counts[idx] for idx in block)
            if overlap_collected + block_tokens <= overlap_tokens:
                overlap_collected += block_tokens
                backtrack_idx -= 1
            else:
                break
                
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

            # Detect chunk type
            chunk_type = _detect_chunk_type(chunk_content)

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
                "chunk_type": chunk_type,  # NEW: Track chunk type
            }

            final_chunks.append({
                "content": chunk_content,
                "metadata": metadata
            })

    return final_chunks
