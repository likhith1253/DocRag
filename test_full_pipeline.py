#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import answer

eval_file = Path("eval/ai_papers_evaluation.json")
with open(eval_file) as f:
    questions_data = json.load(f)

print("\nFULL PIPELINE TEST\n" + "="*60)

results = []

for idx, item in enumerate(questions_data, 1):
    q = item["question"][:50]
    print(f"Q{idx}: {q}...", end=" ", flush=True)
    
    try:
        result = answer(item["question"])
        # answer() returns tuple (answer_text, latency_breakdown)
        if isinstance(result, tuple):
            ans = result[0]
        else:
            ans = result
        
        if ans and len(ans.strip()) > 20:
            print("OK")
            results.append((idx, True, None))
        else:
            print("FAIL")
            results.append((idx, False, "Short answer"))
    except Exception as e:
        print("ERR")
        results.append((idx, False, str(e)[:40]))

print("\n" + "="*60)
passed = sum(1 for _, p, _ in results if p)
print(f"RESULT: {passed}/{len(results)}")

for qid, p, err in results:
    status = "OK" if p else f"FAIL ({err})"
    print(f"Q{qid}: {status}")
