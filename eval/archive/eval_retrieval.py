#!/usr/bin/env python3
"""
Fast evaluation: test retrieval for AI paper questions.
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

print("\nRETRIEVAL EVALUATION\n" + "="*60)
results = []

for idx, item in enumerate(questions_data[:14], 1):
    paper = item["paper"]
    question = item["question"]
    
    print(f"Q{idx}: {question[:50]}...", end=" ")
    sys.stdout.flush()
    
    try:
        # Retrieve chunks for this question
        result = search_vector(question, top_k=10)
        if isinstance(result, tuple):
            chunks = result[0]
        else:
            chunks = result
        
        # Check if top result is from the expected paper
        if chunks:
            top_paper = chunks[0].get("metadata", {}).get("file", "")
            expected = f"papers/AI/{paper}"
            
            # Check if expected paper is in top 5
            found = False
            for i, chunk in enumerate(chunks[:5]):
                file_path = chunk.get("metadata", {}).get("file", "")
                if expected in file_path:
                    found = True
                    rank = i + 1
                    break
            
            if found:
                print(f"OK (rank {rank})")
                results.append((idx, True, rank))
            else:
                print(f"NOT_FOUND")
                results.append((idx, False, 0))
        else:
            print(f"NO_RESULTS")
            results.append((idx, False, 0))
    except Exception as e:
        print(f"ERR")
        results.append((idx, False, 0))

print("\n" + "="*60)
passed = sum(1 for _, p, _ in results if p)
total = len(results)
print(f"RESULT: {passed}/{total} questions retrieved from correct paper")

for qid, passed, rank in results:
    status = f"OK (rank {rank})" if passed else "FAIL"
    print(f"Q{qid}: {status}")
