#!/usr/bin/env python3
"""
Fast direct evaluation: No complex metrics, just show:
Q# | Question | Retrieved Chunks | LLM Answer | Pass/Fail
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval.vector_search import search_vector
from agents.orchestrator import Orchestrator

# Load questions
with open('eval/ai_papers_evaluation.json') as f:
    questions = json.load(f)

orch = Orchestrator()

print("\n" + "="*120)
print("DEBUG EVALUATION - ACTUAL RETRIEVAL + LLM OUTPUT")
print("="*120 + "\n")

for i, q in enumerate(questions, 1):
    qtext = q['question']
    paper = q['paper']
    
    print(f"\nQ{i}: {qtext[:80]}...")
    print(f"Expected Paper: {paper}")
    print("-" * 120)
    
    # Get retrieval
    result = search_vector(qtext, top_k=5)
    if isinstance(result, tuple):
        chunks = result[0]
    else:
        chunks = result
    
    # Show retrieved chunks
    print("RETRIEVED CHUNKS:")
    for j, chunk in enumerate(chunks[:3], 1):
        meta = chunk.get('metadata', {})
        section = meta.get('section', '?')
        title = meta.get('title', '?')[:50]
        content = chunk.get('content', '')[:100].replace('\n', ' ').encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        print(f"  [{j}] {section:30s} | {title:50s}")
        print(f"      {content}...")
    
    # Get LLM answer
    try:
        result = orch.answer(qtext)
        llm_out = result.get('answer', 'ERROR')[:200].replace('\n', ' ').encode('utf-8', errors='replace').decode('utf-8', errors='replace')
    except Exception as e:
        llm_out = f"ERROR: {str(e)[:100]}"
    
    print(f"LLM ANSWER: {llm_out}...")
    print()

print("\n" + "="*120)
