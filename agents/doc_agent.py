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
    seen_chunk_ids = set()
    unique_chunks = []
    
    print("\n" + "=" * 60, flush=True)
    print("PROMPT BUILDER INSTRUMENTATION: CONTEXT ASSEMBLY", flush=True)
    print("=" * 60, flush=True)
    
    # Verify only selected chunks are inserted and each appears ONCE
    for idx, chunk in enumerate(chunks, start=1):
        cid = str(chunk.get("id") or chunk.get("metadata", {}).get("hash") or f"chunk_{idx}")
        if cid in seen_chunk_ids:
            print(f"[PROMPT BUILDER WARNING] Duplicate chunk insertion detected! Chunk ID '{cid}' skipped.", flush=True)
            continue
        seen_chunk_ids.add(cid)
        unique_chunks.append(chunk)

    print(f"Input chunks count: {len(chunks)} | Unique selected chunks: {len(unique_chunks)}", flush=True)
    
    current_prompt_len = 0
    expected_char_count = 0
    
    for i, chunk in enumerate(unique_chunks, start=1):
        meta = chunk.get("metadata", {})
        citation = _format_citation(meta)
        content = str(chunk.get("content", "")).strip()
        
        # Detect prompt self-concatenation / recursive appends in chunk content
        if "CRITICAL RULES:" in content or "Document Excerpts:" in content or "Answer strictly from the excerpts" in content:
            print(f"[PROMPT BUILDER WARNING] Recursive prompt self-concatenation detected in chunk {i}! Stripping prompt boilerplate.", flush=True)
            if "Document Excerpts:" in content:
                content = content.split("Document Excerpts:")[0].strip()

        # Enforce maximum excerpt characters
        if len(content) > _MAX_EXCERPT_CHARS:
            content = content[:_MAX_EXCERPT_CHARS] + "\n...[truncated]"

        appended_text = f"[EXCERPT {i}] {citation}\n{content}"
        appended_len = len(appended_text)
        
        print(f"Current prompt length: {current_prompt_len}", flush=True)
        print(f"What is being appended: Excerpt {i} ({citation})", flush=True)
        print(f"Length of appended text: {appended_len}", flush=True)
        
        new_prompt_len = current_prompt_len + appended_len + (2 if current_prompt_len > 0 else 0)
        print(f"New prompt length: {new_prompt_len}\n", flush=True)
        
        current_prompt_len = new_prompt_len
        expected_char_count += appended_len + (2 if i > 1 else 0)
        parts.append(appended_text)

    context_block = "\n\n".join(parts)
    actual_char_count = len(context_block)
    diff = actual_char_count - expected_char_count
    
    print(f"Expected character count (Context Block): {expected_char_count}", flush=True)
    print(f"Actual character count (Context Block): {actual_char_count}", flush=True)
    print(f"Difference: {diff}", flush=True)
    print("=" * 60, flush=True)
    
    return context_block


def _build_grounding_prompt(question: str, context_block: str) -> str:
    """
    Construct the grounding-enforced prompt with strict instruction.
    """
    sep = "=" * 80
    system_rules = (
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
    )
    user_suffix = (
        "\n" + sep + "\n\n"
        + f"Question: {question}\n\n"
        + "Answer strictly from the excerpts above. Do not use outside knowledge:"
    )

    print("\n" + "=" * 60, flush=True)
    print("PROMPT BUILDER INSTRUMENTATION: GROUNDING PROMPT ASSEMBLY", flush=True)
    print("=" * 60, flush=True)
    
    current_len = 0
    
    # Append 1: System Rules
    app_len1 = len(system_rules)
    print(f"Current prompt length: {current_len}", flush=True)
    print(f"What is being appended: System Rules & Header", flush=True)
    print(f"Length of appended text: {app_len1}", flush=True)
    current_len += app_len1
    print(f"New prompt length: {current_len}\n", flush=True)
    
    # Append 2: Separator 1
    app_len2 = len(sep) + 1
    print(f"Current prompt length: {current_len}", flush=True)
    print(f"What is being appended: Top Separator Line", flush=True)
    print(f"Length of appended text: {app_len2}", flush=True)
    current_len += app_len2
    print(f"New prompt length: {current_len}\n", flush=True)
    
    # Append 3: Context Block
    app_len3 = len(context_block)
    print(f"Current prompt length: {current_len}", flush=True)
    print(f"What is being appended: Context Block ({app_len3} chars)", flush=True)
    print(f"Length of appended text: {app_len3}", flush=True)
    current_len += app_len3
    print(f"New prompt length: {current_len}\n", flush=True)
    
    # Append 4: User Suffix
    app_len4 = len(user_suffix)
    print(f"Current prompt length: {current_len}", flush=True)
    print(f"What is being appended: Bottom Separator & User Question Suffix", flush=True)
    print(f"Length of appended text: {app_len4}", flush=True)
    current_len += app_len4
    print(f"New prompt length: {current_len}\n", flush=True)

    expected_char_count = app_len1 + app_len2 + app_len3 + app_len4
    actual_char_count = current_len
    diff = actual_char_count - expected_char_count

    print(f"Expected character count (Final Prompt): {expected_char_count}", flush=True)
    print(f"Actual character count (Final Prompt): {actual_char_count}", flush=True)
    print(f"Difference: {diff}", flush=True)
    print("=" * 60 + "\n", flush=True)

    return (
        system_rules
        + sep + "\n"
        + context_block
        + user_suffix
    )


def run(question: str, chunks: List[Dict[str, Any]], request_id: str = "default") -> str:
    """
    Run the document QA agent on a question and retrieved chunks.

    Args:
        question: User's natural language question.
        chunks: List of retrieved chunk dicts from the retrieval pipeline.
                Each must have "content" and "metadata" keys.
        request_id: Unique request ID for stage logging.

    Returns:
        Answer string with inline citations, or the canonical CANNOT_FIND_RESPONSE.
    """
    import time
    from storage.pipeline_logger import log_stage, log_grounding_exit, save_prompt_artifact, save_model_output_artifact, log_exception

    try:
        if not chunks:
            log_grounding_exit(
                request_id=request_id,
                file_path="agents/doc_agent.py",
                function_name="run",
                line_number=108,
                reason="No chunks provided to doc_agent.run",
                condition="not chunks",
                evidence={"question": question, "chunks_len": 0}
            )
            return CANNOT_FIND_RESPONSE

        # Filter out empty chunks
        valid_chunks = [c for c in chunks if c.get("content", "").strip()]
        if not valid_chunks:
            log_grounding_exit(
                request_id=request_id,
                file_path="agents/doc_agent.py",
                function_name="run",
                line_number=119,
                reason="All chunks were empty after whitespace stripping",
                condition="not valid_chunks",
                evidence={"question": question, "input_chunks_len": len(chunks), "valid_chunks_len": 0}
            )
            return CANNOT_FIND_RESPONSE

        # STAGE 8: CONTEXT ASSEMBLY
        t_stage8_start = time.perf_counter()
        context_chunks_log = []
        for i, c in enumerate(valid_chunks, start=1):
            cid = str(c.get("id") or c.get("metadata", {}).get("hash") or f"chunk_{i}")
            doc_name = c.get("metadata", {}).get("file") or c.get("metadata", {}).get("paper_title") or "Unknown"
            content_text = c.get("content", "")
            chars = len(content_text)
            words = len(content_text.split())
            score = float(c.get("score", 0.0))
            sec = c.get("metadata", {}).get("section", "Unknown Section")
            pg_start = c.get("metadata", {}).get("page_start", "?")
            pg_end = c.get("metadata", {}).get("page_end", "?")
            
            context_chunks_log.append({
                "rank": i,
                "chunk_id": cid,
                "filename": doc_name,
                "section": sec,
                "pages": f"{pg_start}–{pg_end}",
                "score": round(score, 6),
                "character_count": chars,
                "word_count": words
            })

        context_block = _build_context_block(valid_chunks)
        t_stage8_end = time.perf_counter()
        stage8_ms = (t_stage8_end - t_stage8_start) * 1000

        stage8_data = {
            "valid_chunk_count": len(valid_chunks),
            "context_block_chars": len(context_block),
            "context_block_words": len(context_block.split()),
            "chunks_entering_prompt": context_chunks_log
        }
        log_stage(request_id, 8, "Context Assembly", stage8_data, latency_ms=stage8_ms)

        # STAGE 9: PROMPT BUILDER
        t_stage9_start = time.perf_counter()
        system_prompt = (
            "You are a research assistant answering questions about academic papers.\n"
            "CRITICAL RULES:\n"
            "1. You MUST answer ONLY using information from the provided excerpts below.\n"
            "2. Do NOT use any outside knowledge, general facts, or assumptions.\n"
            "3. Do NOT invent details, methods, results, or any information.\n"
            "4. Extract and quote specific facts, numbers, methods, and results from excerpts.\n"
            f'5. If information is NOT in the excerpts, respond EXACTLY: "{CANNOT_FIND_RESPONSE}"\n'
            "6. Include citation for every factual claim using format: [Excerpt N]\n"
            "7. Be concise and direct. Quote key phrases from excerpts."
        )
        user_prompt = f"Document Excerpts:\n================================================================================\n{context_block}\n================================================================================\n\nQuestion: {question}\n\nAnswer strictly from the excerpts above. Do not use outside knowledge:"
        full_prompt = _build_grounding_prompt(question, context_block)

        # Save FULL PROMPT artifact (Requirement 5)
        save_prompt_artifact(request_id, full_prompt)

        prompt_chars = len(full_prompt)
        prompt_words = len(full_prompt.split())
        approx_prompt_tokens = int(prompt_words * 1.33)
        approx_question_tokens = int(len(question.split()) * 1.33)
        approx_context_tokens = int(len(context_block.split()) * 1.33)

        t_stage9_end = time.perf_counter()
        stage9_ms = (t_stage9_end - t_stage9_start) * 1000

        stage9_data = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "complete_final_prompt": full_prompt,
            "prompt_size_chars": prompt_chars,
            "prompt_word_count": prompt_words,
            "approx_prompt_token_count": approx_prompt_tokens,
            "approx_question_token_count": approx_question_tokens,
            "approx_context_token_count": approx_context_tokens,
            "truncation_details": {
                "truncated": False,
                "reason": "None. Excerpts capped at 4000 chars each; full prompt fits context window."
            }
        }
        log_stage(request_id, 9, "Prompt Builder", stage9_data, latency_ms=stage9_ms)

        result = generate(
            full_prompt,
            model_key="doc_agent_model",
            chunk_count=len(valid_chunks),
            request_id=request_id,
        )

        # Save raw model output artifact before parsing (Requirement 6)
        save_model_output_artifact(request_id, result)

        # STAGE 11: RAW LLM OUTPUT
        stage11_data = {
            "raw_llm_output": result,
            "output_chars": len(result) if result else 0,
            "output_words": len(result.split()) if result else 0
        }
        log_stage(request_id, 11, "Raw LLM Output", stage11_data, latency_ms=0.0)

        # Post-processing: if LLM returned empty string, return canonical not-found
        if not result or not result.strip():
            log_grounding_exit(
                request_id=request_id,
                file_path="agents/doc_agent.py",
                function_name="run",
                line_number=235,
                reason="LLM generate() returned empty output",
                condition="not result or not result.strip()",
                evidence={"result": result}
            )
            return CANNOT_FIND_RESPONSE

        return result.strip()
    except Exception as e:
        log_exception(e, "doc_agent.run")
        return CANNOT_FIND_RESPONSE


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
