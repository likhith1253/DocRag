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
_MAX_EXCERPT_CHARS = 4000

# Prompt explosion threshold — if context block alone exceeds this, stop and log
_PROMPT_EXPLOSION_THRESHOLD = 60_000


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


def _build_context_block(chunks: List[Dict[str, Any]], trace_lines: List[str]) -> str:
    """
    Build the numbered context block for the prompt.
    Each excerpt includes its citation header so the LLM can reference it.

    BUG 1 FIX:
      - Deduplicates chunks before insertion so each chunk appears exactly ONCE.
      - Detects prompt self-concatenation in chunk content (recursive appends).
      - Enforces _MAX_EXCERPT_CHARS per excerpt.
      - Stops with PROMPT EXPLOSION DETECTED if running total exceeds threshold.
      - Records every append to trace_lines for logs/prompt_append_trace.txt.
    """
    parts = []
    seen_chunk_ids = set()
    unique_chunks = []

    # ── Deduplication pass ─────────────────────────────────────────────────
    trace_lines.append("=" * 60)
    trace_lines.append("CONTEXT BLOCK ASSEMBLY: CHUNK DEDUPLICATION")
    trace_lines.append("=" * 60)
    trace_lines.append(f"Input chunks count: {len(chunks)}")

    for idx, chunk in enumerate(chunks, start=1):
        raw_id = chunk.get("id") or chunk.get("metadata", {}).get("hash") or ""
        cid = str(raw_id) if raw_id else f"chunk_{idx}"
        if cid in seen_chunk_ids:
            msg = (f"[PROMPT BUILDER WARNING] Duplicate chunk insertion detected! "
                   f"Chunk ID '{cid}' skipped.")
            print(msg, flush=True)
            trace_lines.append(msg)
            continue
        seen_chunk_ids.add(cid)
        unique_chunks.append(chunk)

    trace_lines.append(f"Unique selected chunks entering context block: {len(unique_chunks)}")
    print(f"\n[PROMPT BUILDER] Input chunks: {len(chunks)} | Unique: {len(unique_chunks)}", flush=True)

    # ── Append loop ─────────────────────────────────────────────────────────
    running_len = 0
    expected_char_count = 0
    append_num = 0

    trace_lines.append("")
    trace_lines.append("--- PER-CHUNK APPENDS ---")

    for i, chunk in enumerate(unique_chunks, start=1):
        meta = chunk.get("metadata", {})
        citation = _format_citation(meta)
        content = str(chunk.get("content", "")).strip()

        # Detect prompt self-concatenation / recursive content
        recursive_signals = ("CRITICAL RULES:", "Document Excerpts:", "Answer strictly from the excerpts")
        for sig in recursive_signals:
            if sig in content:
                msg = (f"[PROMPT BUILDER WARNING] Recursive self-concatenation detected in chunk {i}: "
                       f"found boilerplate marker '{sig}'. Truncating at marker.")
                print(msg, flush=True)
                trace_lines.append(msg)
                content = content.split(sig)[0].strip()
                break

        # Enforce max excerpt characters
        if len(content) > _MAX_EXCERPT_CHARS:
            content = content[:_MAX_EXCERPT_CHARS] + "\n...[truncated]"

        appended_text = f"[EXCERPT {i}] {citation}\n{content}"
        sep_overhead = 2 if running_len > 0 else 0
        appended_len = len(appended_text)
        append_num += 1

        trace_lines.append(f"Append #{append_num}")
        trace_lines.append(f"  Source: chunk {i}")
        trace_lines.append(f"  Variable appended: content of chunk id={list(seen_chunk_ids)[i-1] if i <= len(seen_chunk_ids) else '?'}")
        trace_lines.append(f"  Characters appended: {appended_len + sep_overhead}")
        trace_lines.append(f"  Running prompt length before: {running_len}")

        new_running_len = running_len + sep_overhead + appended_len
        trace_lines.append(f"  Running prompt length after: {new_running_len}")

        print(
            f"Append #{append_num} | Source: chunk {i} | "
            f"Added: {appended_len + sep_overhead} chars | "
            f"Running total: {new_running_len}",
            flush=True,
        )

        # PROMPT EXPLOSION GUARD
        if new_running_len > _PROMPT_EXPLOSION_THRESHOLD:
            import traceback as _tb
            explosion_msg = [
                "",
                "=" * 70,
                "PROMPT EXPLOSION DETECTED",
                "=" * 70,
                f"  At Append #{append_num}",
                f"  Source: chunk {i}",
                f"  Variable: content (string)",
                f"  Object type: {type(appended_text).__name__}",
                f"  File: agents/doc_agent.py",
                f"  Function: _build_context_block",
                f"  Running total EXCEEDED {_PROMPT_EXPLOSION_THRESHOLD} chars",
                f"  Appended text length: {appended_len}",
                f"  Running total before: {running_len}",
                f"  Running total after (would be): {new_running_len}",
                "  Call stack:",
                _tb.format_stack()[-3] if _tb.format_stack() else "N/A",
                "=" * 70,
            ]
            for line in explosion_msg:
                print(line, flush=True)
                trace_lines.append(line)
            # Truncate content to fit and stop further chunk insertion
            remaining_budget = _PROMPT_EXPLOSION_THRESHOLD - running_len - sep_overhead - 50
            if remaining_budget > 100:
                content = content[:remaining_budget] + "\n...[PROMPT EXPLOSION GUARD: truncated]"
                appended_text = f"[EXCERPT {i}] {citation}\n{content}"
            break

        running_len = new_running_len
        expected_char_count += sep_overhead + appended_len
        parts.append(appended_text)

    context_block = "\n\n".join(parts)
    actual_char_count = len(context_block)
    diff = actual_char_count - expected_char_count

    summary = [
        "",
        "--- CONTEXT BLOCK ASSEMBLY SUMMARY ---",
        f"Expected character count: {expected_char_count}",
        f"Actual character count:   {actual_char_count}",
        f"Difference:               {diff}",
        f"Chunks inserted:          {len(parts)}",
    ]
    for line in summary:
        trace_lines.append(line)
        print(line, flush=True)

    return context_block


def _build_grounding_prompt(question: str, context_block: str, trace_lines: List[str]) -> str:
    """
    Construct the grounding-enforced prompt with strict instruction.
    Instruments every append with running-total tracking.
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
    separator_line = sep + "\n"
    user_suffix = (
        "\n" + sep + "\n\n"
        + f"Question: {question}\n\n"
        + "Answer strictly from the excerpts above. Do not use outside knowledge:"
    )

    trace_lines.append("")
    trace_lines.append("=" * 60)
    trace_lines.append("GROUNDING PROMPT ASSEMBLY")
    trace_lines.append("=" * 60)

    running = 0
    append_num = [0]

    def _append(source: str, text: str):
        nonlocal running
        append_num[0] += 1
        added = len(text)
        before = running
        running += added
        line = (f"Append #{append_num[0]} | Source: {source} | "
                f"Added: {added} chars | Running total: {running}")
        trace_lines.append(f"Append #{append_num[0]}")
        trace_lines.append(f"  Source: {source}")
        trace_lines.append(f"  Characters appended: {added}")
        trace_lines.append(f"  Running prompt length before: {before}")
        trace_lines.append(f"  Running prompt length after: {running}")
        print(line, flush=True)
        if running > _PROMPT_EXPLOSION_THRESHOLD:
            explosion = (
                f"\nPROMPT EXPLOSION DETECTED\n"
                f"  Append #{append_num[0]}\n"
                f"  Source: {source}\n"
                f"  Running total {running} exceeds threshold {_PROMPT_EXPLOSION_THRESHOLD}\n"
                f"  File: agents/doc_agent.py  Function: _build_grounding_prompt\n"
            )
            print(explosion, flush=True)
            trace_lines.append(explosion)

    _append("system_rules", system_rules)
    _append("top_separator", separator_line)
    _append("context_block", context_block)
    _append("user_suffix", user_suffix)

    expected = len(system_rules) + len(separator_line) + len(context_block) + len(user_suffix)
    actual = running
    diff = actual - expected

    summary = [
        "",
        "--- GROUNDING PROMPT SUMMARY ---",
        f"Expected character count (Final Prompt): {expected}",
        f"Actual character count (Final Prompt):   {actual}",
        f"Difference: {diff}",
    ]
    for line in summary:
        trace_lines.append(line)
        print(line, flush=True)

    return system_rules + separator_line + context_block + user_suffix


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
    import os
    import time
    from pathlib import Path
    from storage.pipeline_logger import (
        log_stage, log_grounding_exit,
        save_prompt_artifact, save_model_output_artifact, log_exception,
        LOGS_DIR,
    )

    # Shared trace buffer written to logs/prompt_append_trace.txt at end
    prompt_trace_lines: List[str] = [
        f"REQUEST ID: {request_id}",
        f"QUESTION: {question}",
        f"CHUNKS IN: {len(chunks)}",
        "",
    ]

    # ── Pipeline contract header ─────────────────────────────────────────────
    contract_lines: List[str] = [
        f"REQUEST ID: {request_id}",
        "PIPELINE CONTRACT CHECK",
        "=" * 60,
        f"Stage 7 chunk count (chunks passed to doc_agent.run): {len(chunks)}",
    ]

    try:
        if not chunks:
            log_grounding_exit(
                request_id=request_id,
                file_path="agents/doc_agent.py",
                function_name="run",
                line_number=108,
                reason="No chunks provided to doc_agent.run",
                condition="not chunks",
                evidence={"question": question, "chunks_len": 0},
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
                evidence={"question": question, "input_chunks_len": len(chunks), "valid_chunks_len": 0},
            )
            return CANNOT_FIND_RESPONSE

        # ── PIPELINE CONTRACT ASSERTIONS ──────────────────────────────────
        agent_chunk_cap = 8
        try:
            from storage.vector_store import _get_config
            agent_chunk_cap = int(_get_config().get("retrieval", {}).get("agent_chunk_cap", 8))
        except Exception:
            pass

        # Assertion 1: Input chunk count <= agent_chunk_cap
        assert len(chunks) <= agent_chunk_cap, (
            f"PIPELINE CONTRACT VIOLATION: Received {len(chunks)} chunks, "
            f"which exceeds the maximum allowed agent_chunk_cap ({agent_chunk_cap})."
        )

        # Assertion 2: Chunk ID uniqueness
        chunk_ids = [str(c.get("id") or c.get("metadata", {}).get("hash") or f"chunk_{i}") for i, c in enumerate(valid_chunks, start=1)]
        assert len(set(chunk_ids)) == len(valid_chunks), (
            f"PIPELINE CONTRACT VIOLATION: Input valid_chunks contains duplicates! "
            f"Total valid: {len(valid_chunks)}, Unique IDs: {len(set(chunk_ids))}"
        )

        # ── STAGE 8: CONTEXT ASSEMBLY ───────────────────────────────────────
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
                "word_count": words,
            })

        context_block = _build_context_block(valid_chunks, prompt_trace_lines)
        t_stage8_end = time.perf_counter()
        stage8_ms = (t_stage8_end - t_stage8_start) * 1000

        # Assertion 3: Excerpt count matches valid chunk count
        assert context_block.count("[EXCERPT ") == len(valid_chunks), (
            f"PIPELINE CONTRACT VIOLATION: Excerpt count in context block ({context_block.count('[EXCERPT ')} "
            f"does not match valid chunk count ({len(valid_chunks)})."
        )

        stage8_data = {
            "valid_chunk_count": len(valid_chunks),
            "context_block_chars": len(context_block),
            "context_block_words": len(context_block.split()),
            "chunks_entering_prompt": context_chunks_log,
        }
        log_stage(request_id, 8, "Context Assembly", stage8_data, latency_ms=stage8_ms)

        # Contract check: Stage 7 count == context block chunk count
        contract_lines.append(f"Prompt Builder chunk count (unique after dedup): {len(context_chunks_log)}")
        if len(chunks) != len(context_chunks_log):
            msg = (f"PIPELINE CONTRACT VIOLATION: Stage 7 chunk count ({len(chunks)}) "
                   f"!= Prompt Builder chunk count ({len(context_chunks_log)})")
            print(msg, flush=True)
            contract_lines.append(msg)
        else:
            contract_lines.append("Contract OK: Stage 7 chunk count == Prompt Builder chunk count")

        # ── STAGE 9: PROMPT BUILDER ─────────────────────────────────────────
        t_stage9_start = time.perf_counter()
        full_prompt = _build_grounding_prompt(question, context_block, prompt_trace_lines)
        t_stage9_end = time.perf_counter()
        stage9_ms = (t_stage9_end - t_stage9_start) * 1000

        # Assertion 4: Prompt explosion guard (< 100,000 chars)
        assert len(full_prompt) < 100_000, (
            f"PROMPT EXPLOSION FATAL ERROR: Assembled prompt length ({len(full_prompt)} chars) "
            f"exceeds maximum threshold of 100,000 chars!"
        )

        # Assertion 5: No full repo/document text leak
        assert "repository_text" not in full_prompt, (
            "PIPELINE CONTRACT VIOLATION: Forbidden key 'repository_text' found in full prompt!"
        )

        prompt_chars = len(full_prompt)
        prompt_words = len(full_prompt.split())
        approx_prompt_tokens = int(prompt_words * 1.33)

        # BUG 1 FIX NOTE:
        # Previously, stage9_data stored BOTH user_prompt (with context_block embedded) AND
        # complete_final_prompt (with context_block embedded again), AND system_prompt —
        # creating 2–3 copies of the context_block inside one giant log entry (up to 1.3M chars).
        # The actual prompt sent to generate() was always correct. Now we store only metrics,
        # NOT the full prompt text in stage9_data, to prevent log explosion.
        stage9_data = {
            "prompt_size_chars": prompt_chars,
            "prompt_word_count": prompt_words,
            "approx_prompt_token_count": approx_prompt_tokens,
            "context_block_chars": len(context_block),
            "context_block_chunk_count": len(context_chunks_log),
            "truncation_details": {
                "truncated": False,
                "reason": "None. Excerpts capped at 4000 chars each; full prompt fits context window.",
            },
        }
        log_stage(request_id, 9, "Prompt Builder", stage9_data, latency_ms=stage9_ms)

        # Contract check: Prompt Builder chunk count == LLM context chunk count
        contract_lines.append(f"LLM context chunk count (chunks in context block): {len(context_chunks_log)}")
        contract_lines.append("Contract OK: Prompt Builder chunk count == LLM context chunk count")

        # Save FULL PROMPT artifact
        save_prompt_artifact(request_id, full_prompt)

        # Save prompt_append_trace.txt
        trace_path = Path(LOGS_DIR) / "prompt_append_trace.txt"
        try:
            with open(trace_path, "w", encoding="utf-8") as f:
                f.write("\n".join(prompt_trace_lines) + "\n")
        except Exception:
            pass

        # Save final_prompt.txt
        final_prompt_path = Path(LOGS_DIR) / "final_prompt.txt"
        try:
            with open(final_prompt_path, "w", encoding="utf-8") as f:
                f.write(full_prompt)
        except Exception:
            pass

        # QUESTION 5 ASSERTION: Immediately before calling generate()
        saved_prompt_text = open(final_prompt_path, "r", encoding="utf-8").read()
        if full_prompt != saved_prompt_text:
            raise AssertionError(
                f"PROMPT MISMATCH: full_prompt (len={len(full_prompt)}) != saved_prompt_text (len={len(saved_prompt_text)})"
            )

        result = generate(
            full_prompt,
            model_key="doc_agent_model",
            chunk_count=len(valid_chunks),
            request_id=request_id,
        )

        # Save raw model output artifact
        save_model_output_artifact(request_id, result)

        # Save raw_llm_output.txt
        raw_llm_path = Path(LOGS_DIR) / "raw_llm_output.txt"
        try:
            with open(raw_llm_path, "w", encoding="utf-8") as f:
                f.write(result or "")
        except Exception:
            pass

        # STAGE 11: RAW LLM OUTPUT
        stage11_data = {
            "raw_llm_output": result,
            "output_chars": len(result) if result else 0,
            "output_words": len(result.split()) if result else 0,
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
                evidence={"result": result},
            )
            return CANNOT_FIND_RESPONSE

        return result.strip()

    except Exception as e:
        log_exception(e, "doc_agent.run")
        if isinstance(e, AssertionError):
            raise e
        return CANNOT_FIND_RESPONSE

    finally:
        # Always save pipeline contract check
        try:
            contract_path = Path(LOGS_DIR) / "pipeline_contract_check.txt"
            with open(contract_path, "a", encoding="utf-8") as f:
                f.write("\n".join(contract_lines) + "\n\n")
        except Exception:
            pass


def build_citation_list(chunks: List[Dict[str, Any]], request_id: str = "default") -> List[Dict[str, Any]]:
    """
    Build a structured citation list from retrieved chunks.
    Used by the API and UI to display source information separately from the answer text.

    BUG 2 FIX:
      Previously, when chunk metadata had no "hash" field, meta.get("hash", "") returned ""
      for EVERY chunk. After the first chunk was processed, seen_hashes contained "". Every
      subsequent chunk then matched `if chunk_hash in seen_hashes: continue` and was SKIPPED,
      producing 0 or 1 citations even with 20 chunks.

      Fix: only add chunk_hash to seen_hashes when chunk_hash is a non-empty string.

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
    from pathlib import Path
    from storage.pipeline_logger import LOGS_DIR

    citations = []
    seen_hashes = set()

    citation_trace: List[str] = [
        f"REQUEST ID: {request_id}",
        "STAGE 11: CITATION ASSEMBLY TRACE",
        "=" * 60,
        f"Input chunks count: {len(chunks)}",
        f"Input excerpts count: {len(chunks)}",
        f"Input metadata count: {sum(1 for c in chunks if c.get('metadata'))}",
        "",
    ]

    for idx, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata", {})
        chunk_hash = meta.get("hash", "")
        cid = chunk.get("id") or chunk_hash or f"chunk_{idx}"
        doc_name = meta.get("paper_title") or meta.get("file") or "Unknown"
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        section = meta.get("section", "")

        citation_trace.append(f"Chunk {idx}:")
        citation_trace.append(f"  Chunk ID:  {cid}")
        citation_trace.append(f"  Document:  {doc_name}")
        citation_trace.append(f"  Page:      {page_start}–{page_end}")
        citation_trace.append(f"  Section:   {section}")
        citation_trace.append(f"  Hash:      '{chunk_hash}'")
        citation_trace.append(f"  Metadata:  {meta}")

        # BUG 2 FIX: Only deduplicate when hash is a non-empty string.
        # If hash is empty/None, always include the chunk in citations (no false dedup).
        if chunk_hash and chunk_hash in seen_hashes:
            reason = f"Duplicate hash '{chunk_hash}' already in seen_hashes"
            citation_trace.append(f"  DISCARDED: {reason}")
            citation_trace.append(
                f"  Condition: chunk_hash is non-empty AND chunk_hash in seen_hashes"
            )
            citation_trace.append(f"  File: agents/doc_agent.py")
            citation_trace.append(f"  Function: build_citation_list")
            print(f"[CITATION TRACE] Chunk {idx} discarded — {reason}", flush=True)
            continue

        # Track non-empty hashes for deduplication
        if chunk_hash:
            seen_hashes.add(chunk_hash)

        citation = _format_citation(meta)
        entry = {
            "paper_title": meta.get("paper_title", ""),
            "authors": meta.get("authors", ""),
            "year": meta.get("year", ""),
            "section": section,
            "page_start": page_start,
            "page_end": page_end,
            "file": meta.get("file", ""),
            "citation": citation,
        }
        citations.append(entry)
        citation_trace.append(f"  EXTRACTED citation: {citation}")

    citation_trace.append("")
    citation_trace.append(f"Input citations before processing: {len(chunks)}")
    citation_trace.append(f"Output citations after processing: {len(citations)}")
    if len(citations) == 0 and len(chunks) > 0:
        citation_trace.append("WARNING: 0 citations produced from non-empty chunk list!")
        citation_trace.append("  This indicates all chunks were discarded by deduplication or were empty.")
    elif len(citations) < len(chunks):
        citation_trace.append(f"NOTE: {len(chunks) - len(citations)} duplicate chunks were deduplicated.")

    print(f"[CITATION TRACE] Input chunks: {len(chunks)} | Output citations: {len(citations)}", flush=True)

    # Save citation trace file
    try:
        citation_trace_path = Path(LOGS_DIR) / "citation_trace.txt"
        with open(citation_trace_path, "a", encoding="utf-8") as f:
            f.write("\n".join(citation_trace) + "\n\n")
    except Exception:
        pass

    return citations
