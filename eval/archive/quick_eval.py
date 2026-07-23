#!/usr/bin/env python3
import sys, os, json
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.orchestrator import answer

eval_file = Path("eval/ai_papers_evaluation.json")
expected_file = Path("eval/ai_papers_expected_answers.json")

with open(eval_file) as f:
    questions = json.load(f)
with open(expected_file) as f:
    expected_data = {e["id"]: e for e in json.load(f)}

print("\nQUICK EVAL (Q1-Q5)\n" + "="*100 + "\n")

results = []

for idx in range(5):
    qid = f"Q{idx+1}"
    q = questions[idx]["question"]
    expected = expected_data.get(qid, {})
    
    print(f"{qid}: {q[:60]}...", end=" ", flush=True)
    
    try:
        result = answer(q)
        if isinstance(result, tuple):
            ans = result[0]
        else:
            ans = result
        
        if ans and len(ans.strip()) > 20:
            print("OK")
            results.append((qid, "OK"))
        else:
            print("SHORT")
            results.append((qid, "SHORT"))
    except Exception as e:
        print(f"ERR: {str(e)[:30]}")
        results.append((qid, "ERR"))

print("\n" + "="*100)
print(f"SUMMARY: {sum(1 for _, r in results if r == 'OK')}/{len(results)} OK")
for qid, status in results:
    print(f"{qid}: {status}")
