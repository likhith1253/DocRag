"""
eval/generate_dataset.py
========================
Benchmark Q&A dataset generator for DocumentRAG.

Performance changes vs original:
  - Category processing is parallelised via ThreadPoolExecutor (QA_WORKERS).
  - LLM generation + automated verification run concurrently per category.
  - Human review step is still serialised (cannot be parallelised).
  - Per-category wall-clock time is tracked and reported (min/avg/max).

Quality guarantees are fully preserved:
  - Schema validation, source validation, confidence filtering.
  - Duplicate detection (exact + semantic).
  - Automated LLM verification (hallucination, support).
  - Human review gate.
"""

import os
import json
import sys
import time
import threading
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple

import numpy as np
from sentence_transformers import util

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm.backend import generate
from storage.vector_store import VectorStoreManager

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"
)


def _load_qa_workers() -> int:
    """Read workers.qa_workers from config.yaml, default 2."""
    if not os.path.exists(_CONFIG_PATH):
        return 2
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return max(1, cfg.get("workers", {}).get("qa_workers", 2))


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
CATEGORIES = [
    "Code Search",
    "Data Extraction",
    "Reasoning",
    "Architecture",
    "Debugging",
    "Dependency",
    "Security",
    "Performance",
]

# ---------------------------------------------------------------------------
# Helpers — thread-safe because each call is stateless (LLM I/O)
# ---------------------------------------------------------------------------

def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from an LLM response."""
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def generate_qa_for_category(category: str, context: str) -> Optional[dict]:
    """
    Ask the LLM to generate exactly 1 Q&A pair for *category* grounded in *context*.
    Returns a validated dict or None on failure.
    """
    prompt = f"""You are an expert AI dataset generator.
Generate EXACTLY 1 high-quality Q&A pair for the category '{category}' based strictly on the following repository context.

Context:
{context}

Output your response as a valid JSON object with EXACTLY these keys:
"question": the generated question
"answer": the answer to the question
"category": "{category}"
"sources": list of file paths from the Context that support the answer
"confidence": a float between 0.0 and 1.0 representing your confidence that the answer is perfectly correct and fully supported by the context without any hallucination.

Ensure the answer is factually correct. Return ONLY the raw JSON object. Do not include markdown formatting or backticks.
"""
    response_text = generate(prompt, model_key="reasoning_agent_model")
    try:
        data = json.loads(_strip_code_fences(response_text))
        if isinstance(data, dict) and all(
            k in data for k in ["question", "answer", "category", "sources", "confidence"]
        ):
            if isinstance(data["sources"], list):
                return data
    except Exception as e:
        print(f"[{category}] JSON parse error: {e}")
    return None


def verify_candidate(qa: dict, context: str) -> Tuple[bool, str]:
    """
    Automated LLM-based verification: checks answerability, hallucination,
    source support, and category alignment.
    Returns (passed: bool, reason: str).
    """
    prompt = f"""You are a strict QA auditor. Review the following Q&A pair against the provided context.

Context:
{context}

Q&A Pair:
Question: {qa['question']}
Answer: {qa['answer']}
Category: {qa['category']}
Sources: {qa['sources']}

Verify the following:
1. Question is answerable from retrieved chunks.
2. Answer does not hallucinate information outside retrieved context.
3. Source files actually support the answer.
4. Question belongs to the requested category.

Output ONLY a valid JSON object:
{{
  "pass": true or false,
  "reason": "Brief explanation if false, else 'pass'"
}}
Return ONLY the JSON. Do not include markdown formatting or backticks.
"""
    response_text = generate(prompt, model_key="reasoning_agent_model")
    try:
        data = json.loads(_strip_code_fences(response_text))
        return data.get("pass", False), data.get("reason", "Failed to parse reasoning")
    except Exception:
        return False, "Failed to parse verification response"


def validate_sources(sources: list) -> bool:
    """Check that all cited source files actually exist on disk."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for source in sources:
        if not os.path.exists(os.path.join(project_root, source)):
            return False
    return True


def is_duplicate(
    question: str,
    existing_questions: list,
    existing_embeddings: list,
    encoder,
) -> Tuple[bool, str]:
    """Detect exact-string and semantic (cosine > 0.85) duplicates."""
    if question in existing_questions:
        return True, "Exact match duplicate"
    if not existing_questions:
        return False, ""

    q_emb = encoder.encode(question)
    similarities = util.cos_sim(q_emb, existing_embeddings)[0]
    if len(similarities) > 0 and max(similarities) > 0.85:
        return True, "Semantic duplicate"
    return False, ""


# ---------------------------------------------------------------------------
# Per-category pipeline — runs in a thread
# ---------------------------------------------------------------------------

def _process_category(
    category: str,
    store: VectorStoreManager,
) -> Tuple[str, Optional[dict], str, float]:
    """
    Run the full generation + automated-verification pipeline for one category.

    Returns (category, qa_candidate | None, rejection_reason, elapsed_seconds).
    The human-review step is NOT done here — it happens on the main thread.
    """
    t0 = time.perf_counter()

    retrieved_chunks = store.search(
        f"{category} in python repository architecture code reasoning", top_k=5
    )
    if not retrieved_chunks:
        return category, None, f"{category}: No context chunks", time.perf_counter() - t0

    # Unpack search result — store.search returns (results, timing) or just results
    if isinstance(retrieved_chunks, tuple):
        retrieved_chunks = retrieved_chunks[0]

    context_parts = []
    for i, c in enumerate(retrieved_chunks):
        file_name = c["metadata"].get("file", "Unknown")
        context_parts.append(f"--- Chunk {i+1} (File: {file_name}) ---\n{c['content']}")
    context = "\n\n".join(context_parts)

    qa = generate_qa_for_category(category, context)
    if not qa:
        return category, None, f"{category}: Schema/JSON failed", time.perf_counter() - t0

    # Answer length
    if len(qa["answer"]) > 1500 or len(qa["answer"]) < 10:
        return (
            category, None,
            f"{category}: Answer length unreasonable ({len(qa['answer'])} chars)",
            time.perf_counter() - t0,
        )

    # Source files exist
    if not validate_sources(qa["sources"]):
        return (
            category, None,
            f"{category}: Invalid sources {qa['sources']}",
            time.perf_counter() - t0,
        )

    # Confidence
    conf = float(qa.get("confidence", 0))
    if conf < 0.8:
        return (
            category, None,
            f"{category}: Low confidence ({conf:.2f})",
            time.perf_counter() - t0,
        )

    # Automated LLM verification
    passed_verification, v_reason = verify_candidate(qa, context)
    if not passed_verification:
        return (
            category, None,
            f"{category}: Verification failed — {v_reason}",
            time.perf_counter() - t0,
        )

    # Attach context for the caller's duplicate check (cannot share encoder state here)
    qa["_context"] = context
    return category, qa, "", time.perf_counter() - t0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    store = VectorStoreManager()
    encoder = store.encoder
    output_file = os.path.join(os.path.dirname(__file__), "test_dataset.json")
    qa_workers = _load_qa_workers()

    # Load or init dataset
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                dataset = json.load(f)
            except Exception:
                dataset = []
    else:
        dataset = []

    existing_questions: List[str] = [d["question"] for d in dataset]
    existing_embeddings: list = []
    if existing_questions:
        existing_embeddings = encoder.encode(existing_questions).tolist()

    print(f"\nStarting dataset generation pipeline…")
    print(f"  Categories: {len(CATEGORIES)}")
    print(f"  QA workers: {qa_workers}")
    print(f"  Existing items: {len(dataset)}")

    accepted_count = 0
    rejected_count = 0
    rejection_reasons: List[str] = []
    category_timings: Dict[str, float] = {}

    # -----------------------------------------------------------------------
    # Phase 1 — parallel: LLM generation + automated verification
    # -----------------------------------------------------------------------
    print(f"\n[Phase 1] Generating and verifying candidates in parallel…")
    t_phase1_start = time.perf_counter()

    candidate_results: Dict[str, Tuple[Optional[dict], str, float]] = {}

    with ThreadPoolExecutor(max_workers=qa_workers) as executor:
        future_map = {
            executor.submit(_process_category, cat, store): cat
            for cat in CATEGORIES
        }
        for future in as_completed(future_map):
            cat = future_map[future]
            try:
                _, qa_candidate, reason, elapsed = future.result()
                candidate_results[cat] = (qa_candidate, reason, elapsed)
                category_timings[cat] = elapsed
                status = "✓" if qa_candidate else "✗"
                print(f"  {status} [{cat}]  {elapsed:.1f}s  {reason or 'candidate ready'}")
            except Exception as e:
                candidate_results[cat] = (None, f"{cat}: Unexpected error — {e}", 0.0)
                print(f"  ✗ [{cat}] Error: {e}")

    t_phase1 = time.perf_counter() - t_phase1_start
    print(f"\n[Phase 1] Done in {t_phase1:.1f}s")

    # -----------------------------------------------------------------------
    # Phase 2 — serial: duplicate check + human review (order by CATEGORIES)
    # -----------------------------------------------------------------------
    print(f"\n[Phase 2] Human review…")

    for category in CATEGORIES:
        qa_candidate, reason, elapsed = candidate_results.get(
            category, (None, f"{category}: missing result", 0.0)
        )

        print(f"\n{'='*40}")
        print(f"Category: {category}  (generated in {elapsed:.1f}s)")
        print(f"{'='*40}")

        if qa_candidate is None:
            print(f"  Auto-rejected: {reason}")
            rejected_count += 1
            rejection_reasons.append(reason)
            continue

        # Duplicate detection (must run on main thread — modifies shared state)
        is_dup, dup_reason = is_duplicate(
            qa_candidate["question"], existing_questions, existing_embeddings, encoder
        )
        if is_dup:
            print(f"  Reject: {dup_reason}")
            rejected_count += 1
            rejection_reasons.append(f"{category}: {dup_reason}")
            continue

        # Human review
        qa = qa_candidate
        conf = float(qa.get("confidence", 0))
        print("\n--- Human Verification ---")
        print(f"Category:   {qa['category']}")
        print(f"Question:   {qa['question']}")
        print(f"Answer:     {qa['answer']}")
        print(f"Sources:    {qa['sources']}")
        print(f"Confidence: {conf:.2f}")

        while True:
            user_input = input("\nAccept this Q&A pair? (y/n/skip): ").strip().lower()
            if user_input in ("y", "yes", "n", "no", "skip"):
                break
            print("Invalid input. Enter y, n, or skip.")

        if user_input in ("y", "yes"):
            qa_to_save = {k: v for k, v in qa.items() if k not in ("confidence", "_context")}
            dataset.append(qa_to_save)
            existing_questions.append(qa["question"])
            if not existing_embeddings:
                existing_embeddings = encoder.encode([qa["question"]]).tolist()
            else:
                new_emb = encoder.encode([qa["question"]]).tolist()[0]
                existing_embeddings.append(new_emb)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(dataset, f, indent=2)
            accepted_count += 1
            print("  Accepted ✓")
        else:
            rejected_count += 1
            rejection_reasons.append(f"{category}: Human rejected")
            print("  Rejected.")

    # -----------------------------------------------------------------------
    # Summary with per-category timing stats
    # -----------------------------------------------------------------------
    timings = list(category_timings.values())
    print(f"\n{'='*50}")
    print(f"Run Complete")
    print(f"{'='*50}")
    print(f"Categories attempted:  {len(CATEGORIES)}")
    print(f"Accepted:              {accepted_count}")
    print(f"Rejected:              {rejected_count}")
    if timings:
        print(
            f"Generation time:       "
            f"min={min(timings):.1f}s  "
            f"avg={sum(timings)/len(timings):.1f}s  "
            f"max={max(timings):.1f}s"
        )
    print(f"Phase 1 wall-clock:    {t_phase1:.1f}s  ({qa_workers} workers)")
    if rejection_reasons:
        print("\nRejection reasons:")
        for r in rejection_reasons:
            print(f"  - {r}")


if __name__ == "__main__":
    main()
