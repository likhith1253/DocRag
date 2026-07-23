# Pilot Metric Audit Report

**Audit Target**: DocumentRAG Metric Calculations & Mathematical Formulations  
**Date**: July 22, 2026  

---

## Metric Audit Summary

| Metric | Original Formula | Issue Identified | Redesigned / Fixed Formula | Verification Status |
|---|---|---|---|---|
| **Grounding** | `(Supported + 0.5*Partially) / Valid` | Excludes verification failures | `(Supported + 0.5*Partially) / Total Extracted Claims` | Validated |
| **Semantic Similarity** | Cosine similarity of MiniLM embeddings | Paraphrase variance | MiniLM 384d Cosine Similarity * 100 | Validated |
| **Completeness** | Max sentence cosine similarity recall | High paraphrase score despite missing sub-facts | Sentence-level Semantic Recall % | Validated |
| **Hallucination** | `(Not Found / Valid) * 100` | Excludes verification failures | `(Not Found + Contradicted) / Total Claims` | Validated |
| **Retrieved Evidence Coverage** | `min(100, num_chunks * 10)` | Unbounded / Coverage > 100% | `min(100.0, (Relevant / Target Capacity) * 100.0)` | **FIXED & BOUNDED** |
| **Context Precision** | `100 if len >= 5 else 50` | Uniform 100% score | `(Query-Relevant Non-Noise / Total Retrieved) * 100` | **FIXED** |
| **Numerical Accuracy** | 1% relative tolerance match | Robust float regex extractor | Numerical Match % (1% rel / 1e-4 abs) | Validated |
| **Overall Score** | Weighted sum - 0.10 * Hallucination | Relied on flawed sub-scores | Re-weighted with corrected precision/coverage | **FIXED** |

---

