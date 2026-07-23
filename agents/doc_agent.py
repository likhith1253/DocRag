"""
DocumentRAG Document QA Agent.
Answers questions strictly from retrieved document chunks.

Grounding contract:
  - ONLY uses information present in the retrieved excerpts
  - NEVER uses outside knowledge or inferred facts
  - ALWAYS cites the source paper, section, and page for every factual claim
  - Returns the canonical "cannot find" message if no relevant content is found
  
Citation format: [Paper: <title>, Section: <section>, Page: <page>]
"""

from llm.backend import generate
from typing import List, Dict, Any


# Canonical "not found" response — every code path must use this exact string
CANNOT_FIND_RESPONSE = (
    "I cannot find this information in the uploaded documents."
)

# Maximum characters per excerpt to avoid overflowing the context window
# Increased from 2000 to 4000 to preserve variable-value pairs and technical details
_MAX_EXCERPT_CHARS = 4000


def _format_citation(metadata: Dict[str, Any]) -> str:
    """
    Format a citation string from chunk metadata.
    Gracefully handles missing fields.
    """
    title = metadata.get("paper_title") or metadata.get("file", "Unknown Paper")
    section = metadata.get("section") or "Unknown Section"
    page_start = metadata.get("page_start")
    page_end = metadata.get("page_end")

    if page_start and page_end and page_start != page_end:
        page_str = f"Pages {page_start}–{page_end}"
    elif page_start:
        page_str = f"Page {page_start}"
    else:
        page_str = "Page unknown"

    return f"[Paper: {title}, Section: {section}, {page_str}]"


def _build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Build the numbered context block for the prompt.
    Each excerpt includes its citation header so the LLM can reference it.
    """
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata", {})
        citation = _format_citation(meta)
        content = chunk.get("content", "").strip()
        if len(content) > _MAX_EXCERPT_CHARS:
            content = content[:_MAX_EXCERPT_CHARS] + "\n...[truncated]"
        parts.append(f"[EXCERPT {i}] {citation}\n{content}")
    return "\n\n".join(parts)


def _build_grounding_prompt(question: str, context_block: str) -> str:
    """
    Construct the grounding-enforced prompt with strict instruction.
    """
    return (
        "You are a research assistant answering questions about academic papers.\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST answer ONLY using information from the provided excerpts below.\n"
        "2. Do NOT use any outside knowledge, general facts, or assumptions.\n"
        "3. Do NOT invent details, methods, results, or any information.\n"
        "4. Extract and quote specific facts, numbers, methods, and results from excerpts.\n"
        "5. If information is NOT in the excerpts, respond EXACTLY:\n"
        f'   \"{CANNOT_FIND_RESPONSE}\"\n'
        "6. Include citation for every factual claim using format: [Excerpt N]\n"
        "7. Be concise and direct. Quote key phrases from excerpts.\n\n"
        "Document Excerpts:\n"
        "═" * 80 + "\n"
        f"{context_block}\n"
        "═" * 80 + "\n\n"
        f"Question: {question}\n\n"
        "Answer strictly from the excerpts above. Do not use outside knowledge:"
    )


def run(question: str, chunks: List[Dict[str, Any]]) -> str:
    """
    Run the document QA agent on a question and retrieved chunks.

    Args:
        question: User's natural language question.
        chunks: List of retrieved chunk dicts from the retrieval pipeline.
                Each must have "content" and "metadata" keys.

    Returns:
        Answer string with inline citations, or the canonical CANNOT_FIND_RESPONSE.
    """
    if not chunks:
        return CANNOT_FIND_RESPONSE

    # Filter out empty chunks
    valid_chunks = [c for c in chunks if c.get("content", "").strip()]
    if not valid_chunks:
        return CANNOT_FIND_RESPONSE

    context_block = _build_context_block(valid_chunks)
    prompt = _build_grounding_prompt(question, context_block)

    result = generate(
        prompt,
        model_key="doc_agent_model",
        chunk_count=len(valid_chunks),
    )

    # Post-processing: if LLM returned empty string, return canonical not-found
    if not result or not result.strip():
        return CANNOT_FIND_RESPONSE

    return result.strip()


def build_citation_list(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a structured citation list from retrieved chunks.
    Used by the API and UI to display source information separately from the answer text.

    Returns:
        List of citation dicts:
            {
                "paper_title": str,
                "authors": str,
                "year": str,
                "section": str,
                "page_start": int,
                "page_end": int,
                "file": str,
                "citation": str  # formatted citation string
            }
    """
    citations = []
    seen_hashes = set()
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        chunk_hash = meta.get("hash", "")
        if chunk_hash in seen_hashes:
            continue
        seen_hashes.add(chunk_hash)
        citations.append({
            "paper_title": meta.get("paper_title", ""),
            "authors": meta.get("authors", ""),
            "year": meta.get("year", ""),
            "section": meta.get("section", ""),
            "page_start": meta.get("page_start", None),
            "page_end": meta.get("page_end", None),
            "file": meta.get("file", ""),
            "citation": _format_citation(meta),
        })
    return citations
