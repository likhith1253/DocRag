#!/usr/bin/env python3
"""
Evaluate AI papers questions using the DocRag system.
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import answer

# Load evaluation questions
eval_file = Path("eval/ai_papers_evaluation.json")
with open(eval_file, "r", encoding="utf-8") as f:
    questions_data = json.load(f)

print("\nEVALUATION\n" + "="*60)
results = []

for idx, item in enumerate(questions_data[:15], 1):
    paper = item["paper"].replace(".pdf", "").replace("_", " ")
    question = item["question"]
    
    print(f"Q{idx}: {question}", end=" ")
    sys.stdout.flush()
    
    try:
        answer_text = answer(question)
        passed = answer_text and len(answer_text) > 10
        
        if passed:
            print("OK")
            results.append((idx, True, None))
        else:
            print("FAIL")
            results.append((idx, False, "Empty or short answer"))
    except Exception as e:
        print("ERR")
        results.append((idx, False, str(e)[:50]))

print("\n" + "="*60)
print("RESULTS:")
passed = sum(1 for _, p, _ in results if p)
total = len(results)
print(f"{passed}/{total} questions answered")

for qid, passed, error in results:
    status = "OK" if passed else "FAIL"
    print(f"Q{qid}: {status}" + (f" ({error})" if error else ""))
