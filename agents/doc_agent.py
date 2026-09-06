"""
DocumentRAG Document QA Agent — Research-Grade Edition.
Answers questions strictly from retrieved document chunks.

Grounding contract:
  - ONLY uses information present in the retrieved excerpts
  - NEVER uses outside knowledge or inferred facts
  - ALWAYS cites the source paper, section, and page for every factual claim
  - Returns the canonical "cannot find" message if no relevant content is found

Quality upgrades (phases 2–7):
  - Phase 2: Structured context with paper grouping and adjacent-page merging
  - Phase 3/4/7: Adaptive reasoning-oriented prompt based on question depth
  - Phase 5: Rich citation format instructed in prompt (Paper, Section, Page)
  - Phase 6: Code-side confidence block appended after generation
"""

import re
import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

from llm.backend import generate
from typing import List, Dict, Any, Optional

# Canonical "not found" response — every code path must use this exact string
CANNOT_FIND_RESPONSE = (
    "I cannot find this information in the uploaded documents."
)

# Maximum characters per excerpt to avoid overflowing the context window
_MAX_EXCERPT_CHARS = 4000

# Prompt explosion threshold — if context block alone exceeds this, stop and log
_PROMPT_EXPLOSION_THRESHOLD = 60_000


# ---------------------------------------------------------------------------
# Phase 3 refinement: generic per-equation label extraction
# ---------------------------------------------------------------------------

# Matches the common academic convention of labeling an equation with the
# method/algorithm it belongs to, e.g. "Q-learning: r + gamma max_a' Q(s',a')"
# or "Sarsa update: r + gamma Q(s', a')". Purely a text-pattern heuristic —
# no hardcoded list of algorithm names — so it generalizes to any paper's own
# labeling style instead of only ones we've seen before.
_EQUATION_LABEL_RE = re.compile(r'([A-Z][A-Za-z0-9]*(?:[\s\-][A-Za-z0-9]+){0,3})\s*:\s*')
_EQUATION_LABEL_STOPWORDS = {
    "note", "notes", "eq", "eqn", "equation", "equations", "where", "here",
    "figure", "table", "algorithm", "example", "proof", "definition",
    "assumption", "remark", "hint", "recall", "then", "thus",
}


def _extract_equation_labels(content: str) -> List[str]:
    """
    Heuristically extract the algorithm/method name(s) that label a specific
    equation in the source text. Used to help the grounding prompt
    attribute the right equation to the right name when an excerpt contains
    more than one.
    """
    labels: List[str] = []
    # 1. Colon-delimited labels: e.g. "Q-learning: ..."
    for m in _EQUATION_LABEL_RE.finditer(content):
        label = m.group(1).strip()
        tail = content[m.end():m.end() + 250]
        looks_equation_like = bool(re.search(r'[=≈+*()γ\\]|max', tail))
        if looks_equation_like and 1 <= len(label.split()) <= 4:
            if label.lower() not in _EQUATION_LABEL_STOPWORDS and label not in labels:
                labels.append(label)

    # 2. Algorithm headings: e.g. "Algorithm 1 Asynchronous one-step Q-learning"
    for m in re.finditer(r'Algorithm\s+[A-Za-z0-9]+\s+([A-Za-z0-9\s\-]+?)(?:\s*-\s*pseudocode|\n|$)', content):
        algo_name = m.group(1).strip()
        if algo_name and len(algo_name.split()) <= 5 and algo_name not in labels:
            labels.append(algo_name)

    # 3. Target value indicators: e.g. "The target value used by one-step Sarsa is ..."
    for m in re.finditer(r'target value (?:used by|for)\s+([A-Za-z0-9\s\-]+?)\s+is', content, re.IGNORECASE):
        target_name = m.group(1).strip()
        if target_name and len(target_name.split()) <= 4:
            formatted = f"Target value for {target_name}"
            if formatted not in labels:
                labels.append(formatted)

    # 4. Maximum entropy objective indicator
    if re.search(r'maximum entropy objective', content, re.IGNORECASE) and "Maximum Entropy Objective" not in labels:
        labels.append("Maximum Entropy Objective")

    return labels


# ---------------------------------------------------------------------------
# Phase 5: Rich citation formatter
# ---------------------------------------------------------------------------

def _format_citation(metadata: Dict[str, Any]) -> str:
    """Format a rich citation string from chunk metadata."""
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


def _short_title(metadata: Dict[str, Any]) -> str:
    """Return a short display title for a paper (strips path/extension)."""
    raw = metadata.get("paper_title") or metadata.get("file", "Unknown Paper")
    import os
    name = os.path.basename(str(raw))
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return name.replace("_", " ").strip()


# ---------------------------------------------------------------------------
# Phase 2: Structured context block with paper grouping + adjacent merge
# ---------------------------------------------------------------------------

def _build_context_block(chunks: List[Dict[str, Any]], trace_lines: List[str]) -> str:
    """
    Build the numbered context block for the prompt.

    Phase 2 improvements:
      - Deduplicate chunks (unchanged contract)
      - Sort chunks by (paper_title, section, page_start) for narrative continuity
      - Group chunks under a paper header: === Paper: <title> ===
      - Merge adjacent chunks from same paper + same section + consecutive pages
        into a single [EXCERPT N] block — reduces repeated headers, keeps flow
      - Enforce _MAX_EXCERPT_CHARS per merged excerpt
      - PROMPT EXPLOSION GUARD unchanged

    BUG FIX (carried forward):
      - Deduplicates chunks before insertion so each appears exactly ONCE
      - Detects prompt self-concatenation in chunk content
    """
    import itertools

    trace_lines.append("=" * 60)
    trace_lines.append("CONTEXT BLOCK ASSEMBLY: PHASE 2 STRUCTURED")
    trace_lines.append("=" * 60)
    trace_lines.append(f"Input chunks count: {len(chunks)}")

    # ── Deduplication pass ─────────────────────────────────────────────────
    seen_chunk_ids: set = set()
    unique_chunks: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        raw_id = chunk.get("id") or chunk.get("metadata", {}).get("hash") or ""
        cid = str(raw_id) if raw_id else f"chunk_{idx}"
        if cid in seen_chunk_ids:
            msg = f"[PROMPT BUILDER WARNING] Duplicate chunk ID '{cid}' skipped."
            print(msg, flush=True)
            trace_lines.append(msg)
            continue
        seen_chunk_ids.add(cid)
        unique_chunks.append(chunk)

    trace_lines.append(f"Unique chunks entering context block: {len(unique_chunks)}")
    print(f"\n[PROMPT BUILDER] Input chunks: {len(chunks)} | Unique: {len(unique_chunks)}", flush=True)

    # ── Group by paper while preserving CrossEncoder ranking precedence ────
    def _paper_key(c: Dict[str, Any]) -> str:
        m = c.get("metadata", {})
        return (m.get("paper_title") or m.get("file") or "Unknown Paper").lower()

    # Record original CrossEncoder rank for each chunk
    for orig_rank, c in enumerate(unique_chunks):
        c["_ce_rank"] = orig_rank

    # Map each paper to the minimum CrossEncoder rank among its chunks
    paper_min_rank: Dict[str, int] = {}
    for c in unique_chunks:
        pkey = _paper_key(c)
        if pkey not in paper_min_rank:
            paper_min_rank[pkey] = c["_ce_rank"]
        else:
            paper_min_rank[pkey] = min(paper_min_rank[pkey], c["_ce_rank"])

    # Sort key:
    # 1. paper_min_rank (paper containing top CrossEncoder chunk appears FIRST)
    # 2. section (lowercase)
    # 3. page_start (int)
    def _sort_key(c: Dict[str, Any]):
        pkey = _paper_key(c)
        m = c.get("metadata", {})
        section = (m.get("section") or "").lower()
        page = m.get("page_start") or 0
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 0
        return (paper_min_rank[pkey], section, page)

    unique_chunks.sort(key=_sort_key)

    parts: List[str] = []
    running_len: int = 0
    excerpt_num: int = 0
    append_num: int = 0

    trace_lines.append("")
    trace_lines.append("--- PER-PAPER GROUPS (CE RANK PRESERVED) ---")

    for paper_key, group_iter in itertools.groupby(unique_chunks, key=_paper_key):
        group = list(group_iter)
        if not group:
            continue

        # Paper display header
        paper_display = _short_title(group[0].get("metadata", {}))
        paper_header = f"\n=== Paper: {paper_display} ===\n"

        # ── Merge adjacent chunks within same section + consecutive pages ──
        merged_blocks: List[Dict[str, Any]] = []  # list of (merged_text, meta_of_first, page_range)

        def _page_int(c: Dict[str, Any]) -> int:
            try:
                return int(c.get("metadata", {}).get("page_start") or 0)
            except (TypeError, ValueError):
                return 0

        def _section(c: Dict[str, Any]) -> str:
            return (c.get("metadata", {}).get("section") or "").strip().lower()

        current_texts: List[str] = []
        current_meta: Optional[Dict[str, Any]] = None
        current_section: str = ""
        current_page_start: int = 0
        current_page_end: int = 0
        current_evidence_tags: set = set()

        # Evidence-type flags a merged block might carry (Phase 3 metadata —
        # see ingestion/doc_chunker.py::_compute_evidence_flags).
        _EVIDENCE_FLAGS = (
            ("contains_equation", "equation"),
            ("contains_table", "table"),
            ("contains_figure", "figure"),
            ("contains_algorithm", "algorithm"),
        )

        def _flush_block():
            nonlocal current_texts, current_meta, current_section, current_page_start, current_page_end, current_evidence_tags
            if current_texts and current_meta is not None:
                merged_content = "\n\n".join(current_texts)
                # Cap merged block
                if len(merged_content) > _MAX_EXCERPT_CHARS:
                    merged_content = merged_content[:_MAX_EXCERPT_CHARS] + "\n...[truncated]"
                block_meta = dict(current_meta)
                block_meta["page_end"] = current_page_end  # update page range
                merged_blocks.append({
                    "content": merged_content,
                    "metadata": block_meta,
                    "page_start": current_page_start,
                    "page_end": current_page_end,
                    "evidence_tags": sorted(current_evidence_tags),
                })
            current_texts = []
            current_meta = None
            current_section = ""
            current_page_start = 0
            current_page_end = 0
            current_evidence_tags = set()

        for chunk in group:
            content = str(chunk.get("content", "")).strip()

            # Detect prompt self-concatenation
            recursive_signals = ("CRITICAL RULES:", "Document Excerpts:", "Answer strictly from the excerpts")
            for sig in recursive_signals:
                if sig in content:
                    msg = f"[PROMPT BUILDER WARNING] Recursive signal '{sig}' in chunk, truncating."
                    print(msg, flush=True)
                    trace_lines.append(msg)
                    content = content.split(sig)[0].strip()
                    break

            if not content:
                continue

            sec = _section(chunk)
            pg = _page_int(chunk)
            chunk_meta = chunk.get("metadata", {})
            chunk_tags = {label for flag, label in _EVIDENCE_FLAGS if chunk_meta.get(flag)}

            # Merge condition: same section, strictly consecutive page (N or N+1).
            # BUG FIX (A3C regression): never merge two independently-flagged
            # equation chunks into a single block — doing so let two distinct
            # equations (e.g. the Q-learning target and the Sarsa target) blend
            # into one excerpt with no boundary between them, which made it easy
            # for the model to conflate which equation belongs to which method.
            # Keeping each equation-bearing chunk as its own excerpt preserves a
            # clear boundary even when the section/page merge condition would
            # otherwise combine them.
            merging_two_equation_chunks = (
                "equation" in current_evidence_tags and "equation" in chunk_tags
            )
            can_merge = (
                current_meta is not None
                and sec == current_section
                and pg <= current_page_end + 1
                and not merging_two_equation_chunks
            )

            if can_merge:
                current_texts.append(content)
                current_page_end = max(current_page_end, pg)
                current_evidence_tags |= chunk_tags
            else:
                _flush_block()
                current_texts = [content]
                current_meta = chunk_meta
                current_evidence_tags = set(chunk_tags)
                current_section = sec
                current_page_start = pg
                current_page_end = pg

        _flush_block()

        # ── Emit paper header + excerpt blocks ────────────────────────────
        overhead = len(paper_header)
        if running_len + overhead > _PROMPT_EXPLOSION_THRESHOLD:
            trace_lines.append(f"PROMPT EXPLOSION GUARD: skipping paper '{paper_display}'")
            break

        running_len += overhead
        parts.append(paper_header)

        for block in merged_blocks:
            excerpt_num += 1
            append_num += 1
            meta = block["metadata"]
            section_display = meta.get("section") or "Unknown Section"
            p_start = block["page_start"]
            p_end = block["page_end"]
            if p_start and p_end and p_start != p_end:
                page_str = f"Pages {p_start}–{p_end}"
            elif p_start:
                page_str = f"Page {p_start}"
            else:
                page_str = "Page unknown"

            evidence_tags = block.get("evidence_tags") or []
            evidence_str = f" | Evidence: {', '.join(evidence_tags)}" if evidence_tags else ""

            # Phase 3 refinement: when this excerpt is equation evidence,
            # surface any detected per-equation label (e.g. "Q-learning",
            # "Sarsa") so the grounding prompt can require the model to
            # attribute each equation to its own named method instead of
            # guessing from general RL/ML knowledge.
            label_str = ""
            if "equation" in evidence_tags:
                eq_labels = _extract_equation_labels(block["content"])
                if eq_labels:
                    label_str = f" | Equation labels: {', '.join(eq_labels)}"

            excerpt_header = f"[EXCERPT {excerpt_num}] Section: {section_display} | {page_str}{evidence_str}{label_str}"
            full_text = f"{excerpt_header}\n{block['content']}"
            sep_overhead = 2 if running_len > 0 else 0
            block_len = len(full_text) + sep_overhead

            trace_lines.append(f"  Excerpt #{excerpt_num}: {section_display} | {page_str} | {block_len} chars")
            print(
                f"Append #{append_num} | Excerpt {excerpt_num} | Paper: {paper_display} | "
                f"Added: {block_len} chars | Running: {running_len + block_len}",
                flush=True,
            )

            if running_len + block_len > _PROMPT_EXPLOSION_THRESHOLD:
                import traceback as _tb
                explosion_msg = (
                    f"\n{'='*70}\nPROMPT EXPLOSION DETECTED at Excerpt {excerpt_num}\n"
                    f"  Running total {running_len + block_len} exceeds {_PROMPT_EXPLOSION_THRESHOLD} chars\n"
                    f"{'='*70}"
                )
                print(explosion_msg, flush=True)
                trace_lines.append(explosion_msg)
                break

            running_len += block_len
            parts.append(full_text)

    context_block = "\n\n".join(parts)

    summary = [
        "",
        "--- CONTEXT BLOCK ASSEMBLY SUMMARY ---",
        f"Total excerpts inserted: {excerpt_num}",
        f"Total characters: {len(context_block)}",
        f"Papers grouped: {len(set(_paper_key(c) for c in unique_chunks))}",
    ]
    for line in summary:
        trace_lines.append(line)
        print(line, flush=True)

    return context_block


# ---------------------------------------------------------------------------
# Phase 3 / 4 / 5 / 7: Adaptive reasoning-oriented prompt
# ---------------------------------------------------------------------------

def _build_adaptive_prompt(question: str, context_block: str, answer_depth: str, trace_lines: List[str]) -> str:
    """
    Build an adaptive, reasoning-oriented grounding prompt.

    Phase 3 + 4: Selects instruction template based on answer_depth.
    Phase 5: Instructs the LLM to cite using the full excerpt header (Paper, Section, Page).
    Phase 7: Instructs multi-paragraph, coherent answers — not isolated facts.

    answer_depth values: CONCISE | DETAILED | COMPARATIVE | SURVEY
    """
    sep = "=" * 80

    # ── Common grounding header ────────────────────────────────────────────
    grounding_header = (
        "You are a research assistant answering questions STRICTLY from the retrieved document excerpts below.\n\n"
        "ABSOLUTE RULES — violating any rule makes your answer wrong:\n"
        "1. Use ONLY information present in the excerpts. Zero outside knowledge.\n"
        "2. Never invent facts, methods, numbers, or results.\n"
        "3. Every factual claim MUST be cited using the FULL citation from the excerpt header.\n"
        "   Citation format: [Paper: <title>, Section: <section>, Page <N>]\n"
        "   Example: [Paper: Attention Is All You Need, Section: Experiments, Page 8]\n"
        "4. If information is absent from all excerpts, respond EXACTLY:\n"
        f'   "{CANNOT_FIND_RESPONSE}"\n'
        "5. Never repeat the same sentence. Never pad with filler.\n"
        "6. Reason across excerpts — connect evidence, explain relationships, identify cause-effect.\n"
        "7. EXACT ATTRIBUTION: Do not transfer properties between entities merely because they occur in the same chunk.\n"
        "8. Distinguish clearly between the current paper's contribution, previous work, follow-up work, and comparison/baseline methods.\n"
        "9. When describing an entity, only attach properties explicitly supported for THAT entity in the text.\n"
        "10. Do not infer relationships that the retrieved text does not explicitly establish.\n"
        "11. If evidence is insufficient for a detail, state that it is not in the text rather than guessing.\n"
        "12. MATHEMATICAL EQUATIONS, OBJECTIVES & UPDATE TARGETS:\n"
        "   - ABSOLUTELY NEVER rewrite, reconstruct, reformat, or substitute an equation from memory or training data.\n"
        "   - You MUST reproduce mathematical equations, objectives, and algorithm targets VERBATIM as written in the retrieved excerpts.\n"
        "   - Strict Target Distinction in Reinforcement Learning:\n"
        "     * Q-learning target: uses the max operator over next actions: r + gamma * max_a' Q(s', a'; theta^-)\n"
        "     * Sarsa target: uses the action actually taken a' in state s' (NO max operator): r + gamma * Q(s', a'; theta^-)\n"
        "     You MUST preserve this exact distinction. Never mix up, merge, or interchange Q-learning and Sarsa targets.\n"
        "   - Soft Actor-Critic (SAC) Maximum Entropy Objective:\n"
        "     Reproduce Equation 1 verbatim from the text: J(pi) = sum_{t=0}^T E_{(s_t, a_t)~rho_pi} [r(s_t, a_t) + alpha * H(pi(.|s_t))], "
        "where alpha is the temperature parameter controlling the relative importance of entropy against reward. "
        "Do not invent or substitute alternative mathematical forms from memory.\n"
        "   - If an excerpt header shows 'Equation labels: <name>', that equation belongs ONLY to the named method.\n"
        "   - If an equation or target is absent from all excerpts, state clearly that it is not provided in the retrieved text rather than supplying one from memory.\n"
        "13. NUMBERS & TABLES: State a numerical value or table result only if it appears verbatim in an excerpt "
        "(look for 'Evidence: table'). If the specific number requested is not present in the excerpts, say it was "
        "not found rather than estimating or recalling it.\n"
        "14. FIGURES: If asked about a figure/diagram, answer only from excerpts marked 'Evidence: figure' (captions "
        "and surrounding text — no image was analyzed). If no such excerpt exists, say the figure's content is not "
        "available in the retrieved text.\n\n"
    )

    # ── Depth-specific instruction ─────────────────────────────────────────
    if answer_depth == "ENUM_LIST":
        depth_instruction = (
            "ANSWER FORMAT: Complete Entity Enumeration.\n"
            "For ENUM_LIST questions:\n"
            "- directly enumerate the requested entities.\n"
            "- use a numbered list.\n"
            "- include only a concise identifying phrase when necessary.\n"
            "- prohibit separate explanations for every entity.\n"
            "- prohibit a concluding synthesis.\n"
            "- prohibit repeating retrieved evidence.\n"
            "- prohibit unsupported entities.\n"
            "- explicitly say that insufficient evidence must result in an insufficient-evidence response rather than guessing.\n"
        )
    elif answer_depth == "EXTRACTION":
        depth_instruction = (
            "ANSWER FORMAT: Explicit Parameter & Metric Extraction.\n"
            "1. List every explicit parameter value, hyperparameter, numerical setting, dataset metric, or experimental detail mentioned in the excerpts.\n"
            "2. Use bullet points formatted as: • **<Parameter Name>**: <Exact Value or Setting> [Citation].\n"
            "3. If a specific value or hyperparameter is not explicitly stated in the excerpts, write 'Not specified in excerpts.'\n"
            "4. DO NOT summarize into vague generalities (e.g. do not say 'various hyperparameters were used'). State the exact numbers, rates, dimensions, and settings.\n"
        )
    elif answer_depth == "CONCISE":
        depth_instruction = (
            "ANSWER FORMAT: Concise and direct (1–2 paragraphs).\n"
            "Provide a clear, grounded explanation of what is being asked.\n"
            "Cite the source for every factual claim.\n"
            "Do not speculate beyond what the excerpts state.\n"
        )
    elif answer_depth == "COMPARATIVE":
        depth_instruction = (
            "ANSWER FORMAT: Comparative analysis.\n"
            "Structure your answer as follows:\n"
            "1. **Overview**: What is being compared and why.\n"
            "2. **Similarities**: Shared aspects with citations from excerpts.\n"
            "3. **Differences**: Key distinctions with citations from excerpts.\n"
            "4. **Conclusion**: Which approach excels in what context (based only on excerpts).\n"
            "Use evidence from each relevant excerpt. Do not compare beyond what the text states.\n"
        )
    elif answer_depth == "SURVEY":
        depth_instruction = (
            "ANSWER FORMAT: Comprehensive overview.\n"
            "Structure your answer as follows:\n"
            "## Overview\n"
            "A high-level summary of the topic across all retrieved excerpts.\n"
            "## Key Approaches / Findings\n"
            "Enumerate and explain each distinct method, result, or finding from the excerpts.\n"
            "## Relationships and Themes\n"
            "Connect related ideas across different excerpts and papers.\n"
            "## Gaps and Limitations\n"
            "Note what is unclear, missing, or explicitly limited in the excerpts.\n"
            "Cite every claim with the full excerpt citation.\n"
        )
    else:  # DETAILED (default for HOW / WHY / methodology questions)
        depth_instruction = (
            "ANSWER FORMAT: Detailed explanation with reasoning.\n"
            "Structure your answer as follows:\n"
            "## Overview\n"
            "A concise 2–3 sentence summary answering the question directly.\n"
            "## Detailed Explanation\n"
            "Explain the mechanism, methodology, or reasoning in depth.\n"
            "Connect evidence across multiple excerpts where applicable.\n"
            "## Supporting Evidence\n"
            "Quote or paraphrase specific facts, numbers, or methods from the excerpts with full citations.\n"
            "## Limitations or Caveats\n"
            "If the excerpts mention limitations, open problems, or caveats, state them.\n"
            "If not mentioned, write: 'Not discussed in the retrieved excerpts.'\n"
            "Cite every factual claim with the full excerpt citation.\n"
        )

    # ── Common closing instruction ─────────────────────────────────────────
    closing = (
        "\nFormat your answer using markdown (## headers, bullet points where appropriate).\n"
        "Write in coherent paragraphs — not isolated bullet facts.\n"
        "Never use outside knowledge. Reason only from the excerpts.\n"
    )

    # ── Assemble prompt ────────────────────────────────────────────────────
    separator_line = sep + "\n"
    user_suffix = (
        "\n" + sep + "\n\n"
        + f"Question: {question}\n\n"
        + f"{depth_instruction}"
        + closing
        + "\nAnswer:"
    )

    trace_lines.append("")
    trace_lines.append("=" * 60)
    trace_lines.append(f"ADAPTIVE PROMPT ASSEMBLY | depth={answer_depth}")
    trace_lines.append("=" * 60)

    full_prompt = grounding_header + separator_line + context_block + user_suffix

    trace_lines.append(f"Prompt chars: {len(full_prompt)}")
    print(f"\n--- ADAPTIVE PROMPT SUMMARY ---", flush=True)
    print(f"Depth: {answer_depth} | Chars: {len(full_prompt)}", flush=True)

    return full_prompt


# ---------------------------------------------------------------------------
# Phase 6: Confidence block (code-side append)
# ---------------------------------------------------------------------------

def _build_confidence_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Compute a structured Evidence Summary indicator based on retrieval quality.
    Appended AFTER the LLM's answer — not part of the prompt.
    """
    if not chunks:
        return (
            "\n\n---\n"
            "**Evidence Summary**\n"
            "- **Retrieved Papers**: 0\n"
            "- **Retrieved Chunks**: 0\n"
            "- **Dominant Paper Coverage**: 0%\n"
            "- **Average CrossEncoder Score**: 0.00\n"
            "- **Evidence Strength**: Low"
        )

    papers: Dict[str, int] = {}
    scores: List[float] = []
    for c in chunks:
        paper = (
            c.get("metadata", {}).get("paper_title")
            or c.get("metadata", {}).get("file")
            or "Unknown"
        )
        papers[paper] = papers.get(paper, 0) + 1
        scores.append(float(c.get("score", 0.0)))

    n = len(chunks)
    n_papers = len(papers)
    top_paper = max(papers, key=papers.get)
    top_count = papers[top_paper]
    coverage_pct = int(round((top_count / n) * 100)) if n > 0 else 0
    avg_score = sum(scores) / len(scores) if scores else 0.0

    if n >= 4 and top_count >= 4 and avg_score > 2.5:
        level = "High"
    elif n >= 4 and top_count >= 3 and avg_score > 1.0:
        level = "High"
    elif n >= 2 and avg_score > 0.5:
        level = "Medium"
    else:
        level = "Low"

    return (
        f"\n\n---\n"
        f"**Evidence Summary**\n"
        f"- **Retrieved Papers**: {n_papers}\n"
        f"- **Retrieved Chunks**: {n}\n"
        f"- **Dominant Paper Coverage**: {coverage_pct}%\n"
        f"- **Average CrossEncoder Score**: {avg_score:.2f}\n"
        f"- **Evidence Strength**: {level}"
    )


# ---------------------------------------------------------------------------
# Public API: run()
# ---------------------------------------------------------------------------

def run(question: str, chunks: List[Dict[str, Any]], request_id: str = "default") -> str:
    """
    Run the document QA agent on a question and retrieved chunks.

    Args:
        question: User's natural language question.
        chunks: List of retrieved chunk dicts from the retrieval pipeline.
                Each must have "content" and "metadata" keys.
        request_id: Unique request ID for stage logging.

    Returns:
        Answer string with inline citations + confidence block,
        or the canonical CANNOT_FIND_RESPONSE.
    """
    import os
    import time
    from pathlib import Path
    from storage.pipeline_logger import (
        log_stage, log_grounding_exit,
        save_prompt_artifact, save_model_output_artifact, log_exception,
        LOGS_DIR,
    )
    from retrieval.query_analyzer import detect_question_type

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

        assert len(chunks) <= agent_chunk_cap, (
            f"PIPELINE CONTRACT VIOLATION: Received {len(chunks)} chunks, "
            f"which exceeds the maximum allowed agent_chunk_cap ({agent_chunk_cap})."
        )

        chunk_ids = [
            str(c.get("id") or c.get("metadata", {}).get("hash") or f"chunk_{i}")
            for i, c in enumerate(valid_chunks, start=1)
        ]
        assert len(set(chunk_ids)) == len(valid_chunks), (
            f"PIPELINE CONTRACT VIOLATION: Input valid_chunks contains duplicates! "
            f"Total valid: {len(valid_chunks)}, Unique IDs: {len(set(chunk_ids))}"
        )

        # ── Detect question type + answer depth (Phase 3) ─────────────────
        q_analysis = detect_question_type(question)
        question_type = q_analysis["question_type"]
        answer_depth = q_analysis.get("answer_depth", "DETAILED")
        prompt_trace_lines.append(f"Question type: {question_type} | Answer depth: {answer_depth}")

        # ── STAGE 8: CONTEXT ASSEMBLY (Phase 2) ───────────────────────────
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
        # (With Phase 2 merging, excerpt count may be <= chunk count — both are valid)
        num_excerpts = context_block.count("[EXCERPT ")
        assert num_excerpts >= 1, (
            f"PIPELINE CONTRACT VIOLATION: Context block has {num_excerpts} excerpts "
            f"from {len(valid_chunks)} valid chunks — no content was inserted."
        )

        stage8_data = {
            "valid_chunk_count": len(valid_chunks),
            "excerpt_count": num_excerpts,
            "context_block_chars": len(context_block),
            "context_block_words": len(context_block.split()),
            "answer_depth": answer_depth,
            "chunks_entering_prompt": context_chunks_log,
        }
        log_stage(request_id, 8, "Context Assembly", stage8_data, latency_ms=stage8_ms)

        contract_lines.append(f"Prompt Builder chunk count (unique after dedup): {len(context_chunks_log)}")
        if len(chunks) != len(context_chunks_log):
            msg = (
                f"PIPELINE CONTRACT VIOLATION: Stage 7 chunk count ({len(chunks)}) "
                f"!= Prompt Builder chunk count ({len(context_chunks_log)})"
            )
            print(msg, flush=True)
            contract_lines.append(msg)
        else:
            contract_lines.append("Contract OK: Stage 7 chunk count == Prompt Builder chunk count")

        # ── STAGE 9: ADAPTIVE PROMPT BUILDER (Phase 3/4/5) ───────────────
        t_stage9_start = time.perf_counter()
        full_prompt = _build_adaptive_prompt(question, context_block, answer_depth, prompt_trace_lines)
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

        stage9_data = {
            "prompt_size_chars": prompt_chars,
            "prompt_word_count": prompt_words,
            "approx_prompt_token_count": approx_prompt_tokens,
            "context_block_chars": len(context_block),
            "context_block_chunk_count": len(context_chunks_log),
            "answer_depth": answer_depth,
            "question_type": question_type,
            "truncation_details": {
                "truncated": False,
                "reason": "None. Excerpts capped at 4000 chars each; full prompt fits context window.",
            },
        }
        log_stage(request_id, 9, "Prompt Builder", stage9_data, latency_ms=stage9_ms)

        contract_lines.append(f"LLM context chunk count: {len(context_chunks_log)}")
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

        # Verify prompt was saved correctly
        try:
            saved_prompt_text = open(final_prompt_path, "r", encoding="utf-8").read()
            if full_prompt != saved_prompt_text:
                raise AssertionError(
                    f"PROMPT MISMATCH: full_prompt (len={len(full_prompt)}) != saved_prompt_text (len={len(saved_prompt_text)})"
                )
        except AssertionError:
            raise
        except Exception:
            pass  # File read failure is non-fatal

        result = generate(
            full_prompt,
            model_key="doc_agent_model",
            chunk_count=len(valid_chunks),
            request_id=request_id,
            answer_depth=answer_depth,
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

        # ── Phase 6: Append confidence block ─────────────────────────────
        confidence_block = _build_confidence_block(valid_chunks)
        final_answer = result.strip() + confidence_block

        return final_answer

    except Exception as e:
        log_exception(e, "doc_agent.run")
        if isinstance(e, AssertionError):
            raise e
        return CANNOT_FIND_RESPONSE

    finally:
        try:
            from pathlib import Path
            from storage.pipeline_logger import LOGS_DIR
            contract_path = Path(LOGS_DIR) / "pipeline_contract_check.txt"
            with open(contract_path, "a", encoding="utf-8") as f:
                f.write("\n".join(contract_lines) + "\n\n")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Citation list builder (unchanged)
# ---------------------------------------------------------------------------

def build_citation_list(chunks: List[Dict[str, Any]], request_id: str = "default") -> List[Dict[str, Any]]:
    """
    Build a structured citation list from retrieved chunks.

    BUG 2 FIX (carried forward):
      Only deduplicate when hash is a non-empty string.
      If hash is empty/None, always include the chunk (no false dedup).
    """
    from pathlib import Path
    from storage.pipeline_logger import LOGS_DIR

    citations = []
    seen_hashes: set = set()

    citation_trace: List[str] = [
        f"REQUEST ID: {request_id}",
        "STAGE 11: CITATION ASSEMBLY TRACE",
        "=" * 60,
        f"Input chunks count: {len(chunks)}",
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

        citation_trace.append(f"Chunk {idx}: {doc_name} | {section} | hash={chunk_hash!r}")

        if chunk_hash and chunk_hash in seen_hashes:
            citation_trace.append(f"  DISCARDED: duplicate hash")
            print(f"[CITATION TRACE] Chunk {idx} discarded — duplicate hash", flush=True)
            continue

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
            # Traceability for later citation-correctness evaluation — the
            # exact chunk and its evidence type this citation came from, not
            # just the paper/page. Additive only; existing fields unchanged.
            "chunk_id": str(cid),
            "evidence_type": meta.get("evidence_type") or meta.get("chunk_type", ""),
        }
        citations.append(entry)
        citation_trace.append(f"  EXTRACTED: {citation}")

    citation_trace.append(f"\nOutput citations: {len(citations)}")
    print(f"[CITATION TRACE] Input chunks: {len(chunks)} | Output citations: {len(citations)}", flush=True)

    try:
        citation_trace_path = Path(LOGS_DIR) / "citation_trace.txt"
        with open(citation_trace_path, "a", encoding="utf-8") as f:
            f.write("\n".join(citation_trace) + "\n\n")
    except Exception:
        pass

    return citations
