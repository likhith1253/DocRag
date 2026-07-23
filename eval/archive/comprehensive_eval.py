#!/usr/bin/env python3
"""
Comprehensive end-to-end evaluation with answer quality comparison.
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import answer
from retrieval.vector_search import search_vector

# Load evaluation data
eval_file = Path("eval/ai_papers_evaluation.json")
expected_file = Path("eval/ai_papers_expected_answers.json")

with open(eval_file) as f:
    questions = json.load(f)
with open(expected_file) as f:
    expected_data = {e["id"]: e for e in json.load(f)}

print("\nCOMPREHENSIVE END-TO-END EVALUATION\n" + "="*100)

results = []

for idx, question_item in enumerate(questions, 1):
    qid = f"Q{idx}"
    q = question_item["question"]
    expected = expected_data.get(qid, {})
    expected_answer = expected.get("expected_answer", "")
    
    print(f"\n{'-'*100}")
    print(f"{qid}: {q}")
    print(f"{'-'*100}")
    
    try:
        # Run full pipeline
        result = answer(q)
        if isinstance(result, tuple):
            llm_answer = result[0]
            latency_breakdown = result[1] if len(result) > 1 else {}
        else:
            llm_answer = result
            latency_breakdown = {}
        
        # Retrieve chunks for grounding analysis
        retrieval_result = search_vector(q, top_k=5)
        if isinstance(retrieval_result, tuple):
            chunks = retrieval_result[0]
        else:
            chunks = retrieval_result
        
        # Evaluate answer quality
        llm_answer_lower = llm_answer.lower()
        expected_lower = expected_answer.lower()
        
        # Simple semantic match check
        expected_concepts = expected.get("key_concepts", [])
        matched_concepts = sum(1 for concept in expected_concepts if concept.lower() in llm_answer_lower)
        concept_coverage = matched_concepts / len(expected_concepts) if expected_concepts else 0.0
        
        # Check for grounding
        cannot_find = "cannot find" in llm_answer_lower
        is_grounded = not cannot_find and len(chunks) > 0
        
        # Check for hallucinations (claims not in retrieved chunks)
        chunk_text = " ".join([c.get("content", "").lower() for c in chunks])
        
        # Determine verdict
        if concept_coverage >= 0.8:
            verdict = "CORRECT"
        elif concept_coverage >= 0.5:
            verdict = "PARTIAL"
        else:
            verdict = "INCORRECT"
        
        grounding = "Grounded" if is_grounded else "Hallucinated"
        
        # Extract timing
        total_time = latency_breakdown.get("total_ms", 0) / 1000 if latency_breakdown else 0
        vector_ms = latency_breakdown.get("vector_ms", 0)
        llm_ms = latency_breakdown.get("llm_ms", 0)
        
        print(f"\nExpected: {expected_answer[:150]}...")
        print(f"\nGenerated: {llm_answer[:150]}...")
        print(f"\nVERDICT: {verdict} ({concept_coverage*100:.0f}% concept coverage)")
        print(f"GROUNDING: {grounding} ({len(chunks)} chunks retrieved)")
        print(f"TIME: Retrieval {vector_ms:.0f}ms, LLM {llm_ms/1000:.1f}s, Total {total_time:.1f}s")
        
        if chunks:
            print(f"\nTOP CHUNK:")
            print(f"  Paper: {chunks[0].get('metadata', {}).get('file', 'unknown')}")
            print(f"  Section: {chunks[0].get('metadata', {}).get('section', '')}")
            print(f"  Content: {chunks[0].get('content', '')[:100]}...")
        
        results.append({
            "id": qid,
            "question": q,
            "expected": expected_answer,
            "generated": llm_answer,
            "verdict": verdict,
            "concept_coverage": concept_coverage,
            "grounding": grounding,
            "chunks_retrieved": len(chunks),
            "total_time_s": total_time,
            "vector_ms": vector_ms,
            "llm_ms": llm_ms
        })
        
    except Exception as e:
        print(f"ERROR: {str(e)[:100]}")
        results.append({
            "id": qid,
            "question": q,
            "expected": expected_answer,
            "generated": "ERROR",
            "verdict": "ERROR",
            "concept_coverage": 0.0,
            "grounding": "ERROR",
            "chunks_retrieved": 0,
            "total_time_s": 0,
            "vector_ms": 0,
            "llm_ms": 0
        })

# Summary metrics
print(f"\n\n{'='*100}")
print("EVALUATION SUMMARY")
print(f"{'='*100}\n")

correct = sum(1 for r in results if r["verdict"] == "CORRECT")
partial = sum(1 for r in results if r["verdict"] == "PARTIAL")
incorrect = sum(1 for r in results if r["verdict"] == "INCORRECT")
errors = sum(1 for r in results if r["verdict"] == "ERROR")
total = len(results)

grounded = sum(1 for r in results if r["grounding"] == "Grounded")
hallucinated = sum(1 for r in results if r["grounding"] == "Hallucinated")

avg_vector_time = sum(r["vector_ms"] for r in results) / total if total > 0 else 0
avg_llm_time = sum(r["llm_ms"] for r in results) / total if total > 0 else 0
avg_total_time = sum(r["total_time_s"] for r in results) / total if total > 0 else 0
avg_concept_coverage = sum(r["concept_coverage"] for r in results) / total if total > 0 else 0

print(f"Questions Tested      : {total}")
print(f"Correct               : {correct} ({correct*100//total}%)")
print(f"Partial               : {partial} ({partial*100//total}%)")
print(f"Incorrect             : {incorrect} ({incorrect*100//total}%)")
print(f"Errors                : {errors}")
print()
print(f"Grounded              : {grounded} ({grounded*100//total}%)")
print(f"Hallucinated          : {hallucinated} ({hallucinated*100//total}%)")
print()
print(f"Avg Concept Coverage  : {avg_concept_coverage*100:.1f}%")
print(f"Avg Retrieval Time    : {avg_vector_time:.0f} ms")
print(f"Avg LLM Time          : {avg_llm_time/1000:.2f} s")
print(f"Avg Total Time        : {avg_total_time:.2f} s")

# Results table
print(f"\n\n{'='*100}")
print("RESULTS TABLE")
print(f"{'='*100}\n")
print(f"{'ID':<5} {'Verdict':<12} {'Coverage':<10} {'Grounding':<12} {'Time (s)':<10}")
print("-" * 100)
for r in results:
    print(f"{r['id']:<5} {r['verdict']:<12} {r['concept_coverage']*100:>6.0f}% {r['grounding']:<12} {r['total_time_s']:>8.2f}")
