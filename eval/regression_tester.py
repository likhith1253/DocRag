"""
Regression Tester for Production AI Evaluation Platform

Compares current evaluation run outputs against baseline golden runs using
configurable noise tolerances (<= 1.0%) and critical regression gates (>= 5.0%).
"""

import os
import json
from typing import Dict, List, Any

class RegressionTester:
    """Compares current evaluation run output against golden baseline runs."""

    def __init__(self, noise_tolerance_pct: float = 1.0, critical_tolerance_pct: float = 5.0):
        self.noise_tolerance_pct = noise_tolerance_pct
        self.critical_tolerance_pct = critical_tolerance_pct

    def compare_runs(
        self,
        current_data: List[Dict[str, Any]],
        baseline_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        
        current_map = {item.get("question_id") or item.get("id"): item for item in current_data}
        baseline_map = {item.get("question_id") or item.get("id"): item for item in baseline_data}

        critical_regressions = []
        acceptable_variations = []
        improvements = []
        missing_in_current = []

        all_qids = sorted(list(set(list(current_map.keys()) + list(baseline_map.keys()))))

        metric_keys = [
            "overall_score", "grounding_score", "semantic_similarity", "semantic_correctness",
            "retrieval_quality", "context_quality", "numerical_correctness", "completeness", "hallucination_score"
        ]

        for qid in all_qids:
            if qid not in current_map:
                missing_in_current.append(qid)
                continue
            if qid not in baseline_map:
                continue

            cur = current_map[qid]
            base = baseline_map[qid]

            for mkey in metric_keys:
                cur_val = float(cur.get(mkey, cur.get("metrics", {}).get(mkey, 0.0)))
                base_val = float(base.get(mkey, base.get("metrics", {}).get(mkey, 0.0)))

                diff = cur_val - base_val
                if mkey == "hallucination_score":
                    if diff > self.critical_tolerance_pct:
                        critical_regressions.append({
                            "question_id": qid,
                            "metric": mkey,
                            "baseline": base_val,
                            "current": cur_val,
                            "diff": diff,
                            "severity": "CRITICAL"
                        })
                    elif diff > self.noise_tolerance_pct:
                        acceptable_variations.append({
                            "question_id": qid,
                            "metric": mkey,
                            "baseline": base_val,
                            "current": cur_val,
                            "diff": diff,
                            "severity": "NOISE"
                        })
                else:
                    if diff < -self.critical_tolerance_pct:
                        critical_regressions.append({
                            "question_id": qid,
                            "metric": mkey,
                            "baseline": base_val,
                            "current": cur_val,
                            "diff": diff,
                            "severity": "CRITICAL"
                        })
                    elif diff < -self.noise_tolerance_pct:
                        acceptable_variations.append({
                            "question_id": qid,
                            "metric": mkey,
                            "baseline": base_val,
                            "current": cur_val,
                            "diff": diff,
                            "severity": "NOISE"
                        })
                    elif diff > self.noise_tolerance_pct:
                        improvements.append({
                            "question_id": qid,
                            "metric": mkey,
                            "baseline": base_val,
                            "current": cur_val,
                            "diff": diff
                        })

        return {
            "has_critical_regressions": len(critical_regressions) > 0,
            "critical_regression_count": len(critical_regressions),
            "critical_regressions": critical_regressions,
            "acceptable_variations": acceptable_variations,
            "improvements": improvements,
            "missing_in_current": missing_in_current
        }

    def generate_regression_report(self, comparison_result: Dict[str, Any]) -> str:
        lines = []
        lines.append("=== EVALUATION REGRESSION TEST REPORT ===")
        lines.append("")
        if comparison_result["has_critical_regressions"]:
            lines.append(f"🔴 CRITICAL REGRESSIONS DETECTED ({comparison_result['critical_regression_count']} critical drops > {self.critical_tolerance_pct:.1f}%)")
            lines.append("| Question ID | Metric | Baseline | Current | Delta | Severity |")
            lines.append("|---|---|---|---|---|---|")
            for reg in comparison_result["critical_regressions"]:
                lines.append(f"| `{reg['question_id']}` | {reg['metric']} | {reg['baseline']:.2f}% | {reg['current']:.2f}% | {reg['diff']:+.2f}% | {reg['severity']} |")
        else:
            lines.append(f"🟢 PASSED REGRESSION CHECKS: Zero critical regressions detected against baseline (noise tolerance: {self.noise_tolerance_pct:.1f}%).")

        if comparison_result.get("acceptable_variations"):
            lines.append("")
            lines.append(f"🟡 Acceptable Non-Deterministic Noise Variances ({len(comparison_result['acceptable_variations'])} metrics)")
            for var in comparison_result["acceptable_variations"][:5]:
                lines.append(f"  - `{var['question_id']}` {var['metric']}: {var['baseline']:.2f}% -> {var['current']:.2f}% ({var['diff']:+.2f}%)")

        if comparison_result.get("improvements"):
            lines.append("")
            lines.append(f"📈 Metric Improvements ({len(comparison_result['improvements'])} metrics improved)")
            for imp in comparison_result["improvements"][:5]:
                lines.append(f"  - `{imp['question_id']}` {imp['metric']}: {imp['baseline']:.2f}% -> {imp['current']:.2f}% ({imp['diff']:+.2f}%)")

        return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Evaluation Regression Tester")
    parser.add_argument("--current", required=True, help="Path to current evaluation JSON")
    parser.add_argument("--baseline", required=True, help="Path to baseline evaluation JSON")
    parser.add_argument("--noise-tolerance", type=float, default=1.0, help="Noise tolerance percentage (default: 1.0%)")
    parser.add_argument("--critical-tolerance", type=float, default=5.0, help="Critical regression percentage (default: 5.0%)")
    args = parser.parse_args()

    with open(args.current, 'r', encoding='utf-8') as f:
        c_data = json.load(f)
    with open(args.baseline, 'r', encoding='utf-8') as f:
        b_data = json.load(f)

    tester = RegressionTester(noise_tolerance_pct=args.noise_tolerance, critical_tolerance_pct=args.critical_tolerance)
    res = tester.compare_runs(c_data, b_data)
    print(tester.generate_regression_report(res))
