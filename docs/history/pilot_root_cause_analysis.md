# Pilot Root Cause Analysis Report

**Audit Target**: DocumentRAG Evaluation Framework (Questions 1–5)  
**Date**: July 22, 2026  

---

## Issue Severity Classification Matrix

| Issue ID | Category | Severity | Description | Affected Questions | Implementation Status | Engineering Effort | Expected Impact |
|---|---|---|---|---|---|---|---|
| **ISSUE-01** | Similarity Scores | **CRITICAL** | Raw vector score and reranker score were identical constant fallbacks | Q1–Q5 | **FIXED** (Separate compute of FAISS/MiniLM raw vector cosine similarity vs CrossEncoder rerank logits) | 2 hrs | Critical (Verified score independence) |
| **ISSUE-02** | Metric Bound | **HIGH** | Retrieved Evidence Coverage reported values > 100% (e.g. 200%) | Q1–Q5 | **FIXED** (Coverage formula capped at 100.0%) | 1 hr | High (Mathematically bounded metric) |
| **ISSUE-03** | Tier Stopping Policy | **CRITICAL** | Evaluator failed to stop at Tier 1/Tier 2 and escalated every claim to Cross-Evidence | Q1–Q5 | **FIXED** (Enforced early stop when Tier 1/2 confidence >= 70.0%) | 3 hrs | Critical (Correct tier distribution) |
| **ISSUE-04** | Claim Quality | **MEDIUM** | Overly optimistic classification marking all claims as Direct Paper Claims | Q1–Q5 | **FIXED** (Refined thresholds into Direct, Inference, Interpretation, Hallucinated) | 2 hrs | Medium (Realistic claim fidelity) |
| **ISSUE-05** | Context Precision | **MEDIUM** | Context precision always reported 100% | Q1–Q5 | **FIXED** (Evaluates query relevance margin per chunk) | 2 hrs | Medium (Realistic precision variance) |
| **ISSUE-06** | Prompt Contamination | **CRITICAL** | Hardcoded RL terms (Replay Buffer) in LLM verifier prompt | Q1–Q5 | **FIXED** (Domain terms removed from verifier prompt) | 1 hr | Critical (Domain-agnostic judge) |

---

