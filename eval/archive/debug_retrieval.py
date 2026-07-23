#!/usr/bin/env python3
"""
Debug: check what's being retrieved for failing questions.
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval.vector_search import search_vector

# Load evaluation questions
eval_file = Path("eval/ai_papers_evaluation.json")
with open(eval_file, "r", encoding="utf-8") as f:
    questions_data = json.load(f)

# Debug Q1 and Q10 which are failing
failing_questions = [0, 9]  # Indices for Q1 and Q10

for idx in failing_questions:
    item = questions_data[idx]
    paper = item["paper"]
    question = item["question"]
    
    print(f"\n{'='*60}")
    print(f"Q{idx+1}: {question}")
    print(f"Expected paper: {paper}")
    print(f"{'='*60}")
    
    # Retrieve chunks for this question
    result = search_vector(question, top_k=10)
    if isinstance(result, tuple):
        chunks = result[0]
    else:
        chunks = result
    
    print(f"Top 10 retrieved chunks:")
    for i, chunk in enumerate(chunks[:10], 1):
        file_path = chunk.get("metadata", {}).get("file", "")
        section = chunk.get("metadata", {}).get("section", "")
        score = chunk.get("score", 0)
        content = chunk.get("content", "")[:80]
        print(f"  [{i}] {file_path.split('/')[-1][:40]:40} | {section:20} | score:{score:.3f}")
        print(f"      {content}...")
