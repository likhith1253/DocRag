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

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

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
    sep = "=" * 80
    return (
        "You are a research assistant answering questions about academic papers.\n\n"
        "CRITICAL RULES:\n"
        "1. You MUST answer ONLY using information from the provided excerpts below.\n"
        "2. Do NOT use any outside knowledge, general facts, or assumptions.\n"
        "3. Do NOT invent details, methods, results, or any information.\n"
        "4. Extract and quote specific facts, numbers, methods, and results from excerpts.\n"
        "5. If information is NOT in the excerpts, respond EXACTLY:\n"
        f'   "{CANNOT_FIND_RESPONSE}"\n'
        "6. Include citation for every factual claim using format: [Excerpt N]\n"
        "7. Be concise and direct. Quote key phrases from excerpts.\n\n"
        "Document Excerpts:\n"
        + sep + "\n"
        + f"{context_block}\n"
        + sep + "\n\n"
        + f"Question: {question}\n\n"
        + "Answer strictly from the excerpts above. Do not use outside knowledge:"
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
        print("=" * 60, flush=True)
        print("EARLY EXIT", flush=True)
        print("=" * 60, flush=True)
        print("Reason: No chunks provided to doc_agent.run", flush=True)
        print("Returned from: doc_agent.py", flush=True)
        print("Line: 101", flush=True)
        return CANNOT_FIND_RESPONSE

    # Filter out empty chunks
    valid_chunks = [c for c in chunks if c.get("content", "").strip()]
    if not valid_chunks:
        print("=" * 60, flush=True)
        print("EARLY EXIT", flush=True)
        print("=" * 60, flush=True)
        print("Reason: All chunks were empty after whitespace stripping", flush=True)
        print("Returned from: doc_agent.py", flush=True)
        print("Line: 106", flush=True)
        return CANNOT_FIND_RESPONSE

    # STAGE 7: CONTEXT ASSEMBLY
    print("=" * 60, flush=True)
    print("STAGE 7: CONTEXT ASSEMBLY", flush=True)
    print("=" * 60, flush=True)
    print(f"Number of chunks sent to LLM: {len(valid_chunks)}", flush=True)
    for i, c in enumerate(valid_chunks, start=1):
        cid = c.get("id") or c.get("metadata", {}).get("hash") or f"chunk_{i}"
        doc_name = c.get("metadata", {}).get("file") or c.get("metadata", {}).get("paper_title") or "Unknown"
        chars = len(c.get("content", ""))
        score = c.get("score", 0.0)
        preview = c.get("content", "")[:300]
        print(f"\n[Chunk {i}]", flush=True)
        print(f"Chunk ID: {cid}", flush=True)
        print(f"Document: {doc_name}", flush=True)
        print(f"Characters: {chars}", flush=True)
        print(f"Score: {score}", flush=True)
        print(f"Context preview:\n{preview}", flush=True)

    context_block = _build_context_block(valid_chunks)
    prompt = _build_grounding_prompt(question, context_block)

    # STAGE 8: PROMPT BUILDER
    prompt_chars = len(prompt)
    prompt_words = len(prompt.split())
    approx_tokens = int(prompt_words * 1.33)
    first_500 = prompt[:500]
    last_500 = prompt[-500:] if len(prompt) >= 500 else prompt

    print("\n" + "=" * 60, flush=True)
    print("STAGE 8: PROMPT BUILDER", flush=True)
    print("=" * 60, flush=True)
    print(f"Prompt size: {prompt_chars} characters | {prompt_words} words | ~{approx_tokens} tokens", flush=True)
    print(f"\n--- First 500 characters ---\n{first_500}", flush=True)
    print(f"\n--- Last 500 characters ---\n{last_500}", flush=True)

    result = generate(
        prompt,
        model_key="doc_agent_model",
        chunk_count=len(valid_chunks),
    )

    # STAGE 10: RESPONSE
    print("\n" + "=" * 60, flush=True)
    print("STAGE 10: LLM RESPONSE", flush=True)
    print("=" * 60, flush=True)
    raw_out = result[:500] if result else "<EMPTY>"
    print(f"Raw LLM output (First 500 chars):\n{raw_out}", flush=True)

    # Post-processing: if LLM returned empty string, return canonical not-found
    if not result or not result.strip():
        print("\n" + "=" * 60, flush=True)
        print("EARLY EXIT", flush=True)
        print("=" * 60, flush=True)
        print("Reason: LLM generate() returned empty output", flush=True)
        print("Returned from: doc_agent.py", flush=True)
        print("Line: 119", flush=True)
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
