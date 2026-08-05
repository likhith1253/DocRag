import sys
sys.path.insert(0, ".")
import json
from scripts.retrieval_audit import run_retrieval_audit

if __name__ == "__main__":
    results = run_retrieval_audit()
    print("=" * 80)
    print("SUMMARY MATRIX:")
    print("=" * 80)
    print(f"{'QID':<5} | {'Category':<20} | {'S1(DB)':<6} | {'S2(V100)':<8} | {'S3(MMR20)':<9} | {'S4(CE8)':<7} | {'S5(Prompt)':<10} | {'S6(LLM)':<7} | {'Failure Stage'}")
    print("-" * 110)
    for r in results:
        s1 = "PASS" if r['stage1_in_db'] else "FAIL"
        s2 = "PASS" if r['stage2_top100_retrieved'] else "FAIL"
        s3 = "PASS" if r['stage3_mmr_retrieved'] else "FAIL"
        s4 = "PASS" if r['stage4_ce_retrieved'] else "FAIL"
        s5 = "PASS" if r['stage5_in_prompt'] else "FAIL"
        s6 = "PASS" if r['stage6_ans_passed'] else "FAIL"
        print(f"{r['qid']:<5} | {r['category']:<20} | {s1:<6} | {s2:<8} | {s3:<9} | {s4:<7} | {s5:<10} | {s6:<7} | {r['failure_stage']}")
