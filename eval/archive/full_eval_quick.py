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

print("\nFULL EVALUATION (14 QUESTIONS)\n" + "="*80 + "\n")

results = []

for idx, q_item in enumerate(questions, 1):
    qid = f"Q{idx}"
    q = q_item["question"]
    expected = expected_data.get(qid, {})
    expected_answer = expected.get("expected_answer", "")
    key_concepts = expected.get("key_concepts", [])
    
    print(f"{qid}: {q[:50]}...", end=" ", flush=True)
    
    try:
        result = answer(q)
        if isinstance(result, tuple):
            ans = result[0]
            latency = result[1] if len(result) > 1 else {}
        else:
            ans = result
            latency = {}
        
        # Evaluate quality
        ans_lower = ans.lower()
        matched = sum(1 for c in key_concepts if c.lower() in ans_lower)
        coverage = matched / len(key_concepts) if key_concepts else 0.0
        
        if coverage >= 0.7:
            verdict = "GOOD"
        elif coverage >= 0.4:
            verdict = "PARTIAL"
        else:
            verdict = "POOR"
        
        print(f"{verdict} ({coverage*100:.0f}%)")
        results.append((qid, verdict, coverage, ans[:100]))
        
    except Exception as e:
        print(f"ERR ({str(e)[:20]})")
        results.append((qid, "ERROR", 0, ""))

print("\n" + "="*80)
good = sum(1 for _, v, _, _ in results if v == "GOOD")
partial = sum(1 for _, v, _, _ in results if v == "PARTIAL")
poor = sum(1 for _, v, _, _ in results if v == "POOR")
error = sum(1 for _, v, _, _ in results if v == "ERROR")
total = len(results)

print(f"\nSUMMARY:")
print(f"  GOOD     : {good:2}/{total} ({good*100//total}%)")
print(f"  PARTIAL  : {partial:2}/{total} ({partial*100//total}%)")
print(f"  POOR     : {poor:2}/{total} ({poor*100//total}%)")
print(f"  ERROR    : {error:2}/{total} ({error*100//total}%)")
print(f"\n  PASS RATE: {(good+partial)*100//total}%")

print("\n" + "-"*80)
print("RESULTS TABLE")
print("-"*80)
print(f"{'ID':<5} {'Verdict':<10} {'Coverage':<12} {'Answer Preview':<50}")
print("-"*80)
for qid, verdict, coverage, ans_preview in results:
    print(f"{qid:<5} {verdict:<10} {coverage*100:>6.0f}%      {ans_preview:<50}")
