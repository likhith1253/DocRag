# Chunk-Only vs Expanded Document Evaluation - Comparison Report

## Critical Change

### Problem with Chunk-Only Evaluation
The previous evaluator judged claims using **only the retrieved chunk snippets**, which are incomplete fragments of the original document. This is incorrect because:
- Chunks are truncated segments that may miss critical context
- OCR text from diagrams might be present in chunks but without surrounding explanation
- Figure captions, tables, and neighboring paragraphs are missing
- A strict human reviewer would always inspect the original paper, not just a snippet

### New Expanded Document Evaluation
The evaluator now:
- Opens the **original PDF** for each candidate chunk
- Extracts the **full page** content including all text blocks
- Includes **neighboring pages** (previous and next) for context
- Extracts **OCR text** from diagrams, figures, and mathematical diagrams
- Extracts **tables** and **figure captions**
- Runs evidence verification on this **richer evidence context**

### Files Modified
- `eval/redesigned_evaluator.py`: Added PDF parsing, expanded evidence extraction, toggle flag

---

## Claim-by-Claim Comparison for Question 1

### Claim 1: Development and application of a Deep Q-learning algorithm specifically designed for ramp metering

**Chunk-Only Evaluation:**
- Grounding Status: PARTIALLY_SUPPORTED
- Confidence: 50.0
- Reason: The evidence mentions a deep reinforcement learning (DRL) method but does not explicitly state that it is specifically designed for ramp metering.
- Key Evidence: Candidate 2 (Page 6) found OCR text: "Figure 4: 4 Approaches for stabilizing the training process in deep Q-learning: a) relay buffer; b) target network." and "Table 1: Deep Q-learning for ramp metering."

**Expanded Document Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks
- Key Evidence: Candidate 2 (Page 6) - OCR text present but LLM did not recognize it as sufficient evidence

**Analysis:** The chunk-only evaluation found OCR evidence in the chunk snippet (Figure 4 caption mentioning "relay buffer" and "target network", Table 1 mentioning "Deep Q-learning for ramp metering"). However, the expanded document evaluation did not find this sufficient to support the claim. This may be because:
1. The OCR text was present in the chunk but when expanded to full page, the LLM focused on other content
2. The OCR extraction from the full page may have been different from the chunk OCR
3. The LLM may have been stricter when evaluating the full page context

**Change:** PARTIALLY_SUPPORTED → NOT_FOUND (downgrade)

---

### Claim 2: Use of an asynchronous method to speed up training, enhancing efficiency

**Chunk-Only Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Expanded Document Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Analysis:** Both evaluations correctly identified that there is no evidence for asynchronous training in the paper.

**Change:** No change (NOT_FOUND → NOT_FOUND)

---

### Claim 3: Balancing exploration and exploitation through replay buffer

**Chunk-Only Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Expanded Document Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Analysis:** Both evaluations correctly identified that while replay buffer is mentioned in OCR (Figure 4), there is no explicit text about balancing exploration and exploitation.

**Change:** No change (NOT_FOUND → NOT_FOUND)

---

### Claim 4: Utilization of raw data and its processed features as inputs for Q-networks

**Chunk-Only Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Expanded Document Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Analysis:** Both evaluations correctly identified that there is no explicit mention of raw data, processed features, or Q-network inputs in the evidence.

**Change:** No change (NOT_FOUND → NOT_FOUND)

---

### Claim 5: Stable training processes through stabilizing mechanisms like replay buffers and target networks

**Chunk-Only Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Expanded Document Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Analysis:** Both evaluations found OCR text mentioning "relay buffer" and "target network" in Figure 4, but neither considered this sufficient to fully support the claim about achieving stable training processes. The OCR text mentions these mechanisms but does not describe how they achieve stability.

**Change:** No change (NOT_FOUND → NOT_FOUND)

---

### Claim 6: These contributions aim to improve the efficiency and effectiveness of ramp meters in managing traffic flow more adaptively and dynamically

**Chunk-Only Evaluation:**
- Grounding Status: NOT_FOUND
- Confidence: 0.0
- Reason: No supporting evidence found after checking all 5 candidate chunks

**Expanded Document Evaluation:**
- Grounding Status: PARTIALLY_SUPPORTED
- Confidence: 80.0
- Reason: The evidence supports the claim that these contributions aim to improve the efficiency and effectiveness of ramp meters in managing traffic flow more adaptively and dynamically, as it mentions learning from video data and better performance compared to traditional methods.
- Quoted Supporting Text: "This study proposes a DRL method for local ramp metering based on traffic video data."

**Analysis:** The expanded document evaluation found additional context in the full page (Page 13, Conclusion) that supports the claim about improving efficiency and effectiveness. The chunk-only evaluation missed this because the chunk snippet was truncated and didn't include the full context of the conclusion paragraph.

**Change:** NOT_FOUND → PARTIALLY_SUPPORTED (upgrade)

---

## Summary of Classification Changes

| Claim | Chunk-Only | Expanded | Change | Reason |
|-------|-----------|----------|--------|--------|
| Claim 1 | PARTIALLY_SUPPORTED | NOT_FOUND | Downgrade | OCR evidence in chunk not recognized in full page context |
| Claim 2 | NOT_FOUND | NOT_FOUND | No change | No evidence in either evaluation |
| Claim 3 | NOT_FOUND | NOT_FOUND | No change | No evidence in either evaluation |
| Claim 4 | NOT_FOUND | NOT_FOUND | No change | No evidence in either evaluation |
| Claim 5 | NOT_FOUND | NOT_FOUND | No change | OCR present but insufficient in both |
| Claim 6 | NOT_FOUND | PARTIALLY_SUPPORTED | Upgrade | Full page context provided additional evidence |

**Total Changes:** 2 out of 6 claims changed classification
- 1 downgrade (Claim 1)
- 1 upgrade (Claim 6)

---

## Grounding Score Comparison

### Chunk-Only Evaluation
- Grounding Score: 16.7/100
- 0 fully supported, 2 partially supported out of 6 valid claims
- Hallucination Score: 66.7/100 (4 out of 6 claims have no supporting evidence)

### Expanded Document Evaluation
- Grounding Score: 16.7/100
- 0 fully supported, 2 partially supported out of 6 valid claims
- Hallucination Score: 66.7/100 (4 out of 6 claims have no supporting evidence)

**Analysis:** Despite the classification changes, the overall grounding score remained the same because:
- Claim 1 downgrade (PARTIALLY_SUPPORTED → NOT_FOUND) was offset by
- Claim 6 upgrade (NOT_FOUND → PARTIALLY_SUPPORTED)

---

## Key Findings

### 1. OCR Text Recognition Inconsistency
The chunk-only evaluation found OCR evidence in Claim 1 (Figure 4 caption and Table 1) that the expanded evaluation did not recognize. This suggests:
- OCR text extraction may differ between chunk-level and page-level parsing
- The LLM may be more lenient when evaluating smaller chunks
- The LLM may be stricter when evaluating larger contexts

### 2. Context Matters
Claim 6 was upgraded from NOT_FOUND to PARTIALLY_SUPPORTED because the expanded document evaluation included the full conclusion paragraph from Page 13, which provided context about improving efficiency and effectiveness that was missing from the truncated chunk.

### 3. No Clear Winner
The expanded document evaluation did not consistently improve results:
- It found additional evidence for Claim 6 (upgrade)
- But it failed to recognize OCR evidence for Claim 1 (downgrade)
- This suggests the PDF parsing or LLM evaluation needs refinement

---

## Recommendations

### 1. Improve OCR Extraction
The OCR text extraction from full PDF pages should be consistent with chunk-level OCR. The fact that Figure 4's caption was recognized in the chunk but not in the full page suggests a parsing inconsistency.

### 2. Refine LLM Prompt for Expanded Context
The LLM prompt may need adjustment to better handle larger evidence contexts. The current strict prompt may be too restrictive when evaluating full pages.

### 3. Add Figure Caption Extraction
Explicitly extract and include figure captions separately from the main text to ensure they are not lost in the expanded context.

### 4. Verify PDF Parsing
The PDF parser should be verified to ensure it correctly extracts all text blocks, including OCR text from diagrams and figures.

---

## Conclusion

The expanded document evaluation is conceptually correct - a strict human reviewer would inspect the original paper, not just truncated chunks. However, the current implementation has issues:
- OCR extraction inconsistency between chunk and page levels
- LLM evaluation may be too strict with larger contexts
- No clear improvement in overall grounding score

The evaluator should behave like a reviewer reading the paper itself, but the implementation needs refinement to ensure consistent OCR extraction and appropriate LLM evaluation of expanded contexts.
