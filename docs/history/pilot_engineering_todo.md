# Pilot Engineering TODO List

**Audit Target**: Evaluator Fixes & HPC Benchmark Readiness Backlog  
**Date**: July 22, 2026  

---

| Priority | Component | Issue Description | Status | Effort | Impact |
|---|---|---|---|---|---|
| **Priority 1** | Score Independence | Separate computation of Raw Vector Similarity vs CrossEncoder Rerank Logits | **COMPLETED** | 2 hrs | Critical |
| **Priority 1** | Metric Bounding | Cap Retrieved Evidence Coverage strictly at 100.0% | **COMPLETED** | 1 hr | High |
| **Priority 1** | Tier Stopping Policy | Stop verification at Tier 1 / Tier 2 when confidence >= 70% | **COMPLETED** | 3 hrs | Critical |
| **Priority 2** | Claim Fidelity | Refine overlap thresholds for Direct, Inference, Interpretation, Hallucination | **COMPLETED** | 2 hrs | Medium |
| **Priority 2** | Context Precision | Compute precision based on query relevance margin per chunk | **COMPLETED** | 2 hrs | Medium |
| **Priority 3** | HPC Deployment | Scale verified evaluator pipeline to Questions 6–40 | **PENDING HPC** | 4 hrs | High |

---

