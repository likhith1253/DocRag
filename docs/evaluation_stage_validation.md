# Production AI Evaluation Platform Architecture Documentation (8-Stage Pipeline)

This document describes the production-grade 8-stage evaluation platform for **DocumentRAG / DocRag**. The platform converts evaluation into 8 independent, deterministic validation stages (Stage 0 through Stage 7) with explicit input/output serialization, provenance versioning, RAG retrieval diagnostics, canonical claim construction, confidence calibration analysis, configurable regression tolerances, system acceptance gates, and subsystem diagnostic reporting.

---

## 1. 8-Stage Pipeline Architecture & Subsystem Breakdown

```
 [Stage 0: Gold Ref] -------------> (Semantic Gold Claims & Metric Bounds)
         │                                       │
 [Stage 1: Retrieval Diag] -------> (Recall@K, MRR, nDCG, Gold Chunk Rank)
         │                                       │
 [Stage 2: Rerank Diag] ----------> (scored_chunks)
         │                                       │
 [Stage 3: Canonical Claims] -----> (CanonicalClaimSet: claim_001_a8f3b)
         │                                       │
 [Stage 4: Evidence & ECE] -------> (verified_claims & Calibration ECE) ───┐
                                                                            │
 [Stage 5: Metric Computation] <-- (8 Bounded Metrics & Overall Score) ────┤
         │                                                                  │
 [Stage 6: Acceptance Gates]   <-- (AcceptanceStatus: ACCEPTED / REJECTED) ─┘
         │
 [Stage 7: Report Generation]  <-- (QuestionReport & Markdown Audit Report)
```

### Stage 0: Gold Reference Validation Stage (`GoldReferenceValidationStage`)
- **File**: `eval/stages/gold_reference_stage.py`
- **Purpose**: Validates ground-truth datasets, semantic expected claims, gold evidence chunk IDs (`gold_chunk_ids`), expected grounding labels, and metric range bounds before pipeline execution.
- **Inputs**: `question_id`, `paper`, `question`, `expected_answer`, `expected_claims`, `gold_chunk_ids`, `expected_metric_ranges`
- **Outputs**: `GoldReference` specification object

### Stage 1: Retrieval Diagnostics Stage (`RetrievalValidationStage`)
- **File**: `eval/stages/retrieval_stage.py`
- **Purpose**: Validates vector store / RAG retrieval output and computes retrieval quality diagnostics against gold chunks:
  - `gold_retrieved`: (Bool)
  - `gold_chunk_rank`: (1-indexed rank or null)
  - `recall_at_k`: Recall@K for $K \in \{1, 3, 5, 10\}$
  - `mrr`: Mean Reciprocal Rank ($1 / \text{rank}$)
  - `ndcg`: Normalized Discounted Cumulative Gain
- **Inputs**: `question`, `paper`, `retrieved_chunks`, `gold_chunk_ids`, `max_capacity`
- **Outputs**: `retrieved_chunks`, retrieval quality diagnostics

### Stage 2: Reranker & Scoring Stage (`RerankerValidationStage`)
- **File**: `eval/stages/reranker_stage.py`
- **Purpose**: Computes MiniLM raw vector cosine similarity and CrossEncoder rerank scores with sigmoid normalization.
- **Inputs**: `question`, `retrieved_chunks`, `vector_sim_fn`, `rerank_score_fn`
- **Outputs**: `scored_chunks` containing `raw_vector_score`, `rerank_score`, `normalized_score`
- **Invariants**: Sigmoid normalized score bounded in $[0.0, 1.0]$, raw vector vs rerank score distinction, non-constant score variance.

### Stage 3: Canonical Claim Construction Stage (`ClaimExtractionStage`)
- **File**: `eval/stages/claim_extraction_stage.py`
- **Purpose**: Extracts claims and constructs a stable `CanonicalClaimSet` representation (`canonical_id`, `claim_hash`, `normalized_text`, `claim_type`) to decouple downstream metrics from raw extraction variations.
- **Inputs**: `raw_llm_answer`, `extract_claims_fn`
- **Outputs**: `CanonicalClaimSet`

### Stage 4: Evidence Verification & Calibration Stage (`EvidenceVerificationStage`)
- **File**: `eval/stages/evidence_verification_stage.py`
- **Purpose**: Evaluates candidate evidence grounding across Tier 1, Tier 2, and Tier 3 with bigram claim fidelity labels, and computes **Confidence Calibration Analysis** (Expected Calibration Error - ECE & reliability binning).
- **Inputs**: `claims`, `scored_chunks`, `paper`, `use_expanded_evidence`
- **Outputs**: Verified claims and `calibration_summary` (ECE & reliability bins)

### Stage 5: Metric Computation Stage (`MetricComputationStage`)
- **File**: `eval/stages/metric_computation_stage.py`
- **Purpose**: Consumes `CanonicalClaimSet` and computes 8 core metrics, hallucination penalty, and overall score.
- **Inputs**: `expected_answer`, `raw_llm_answer`, `CanonicalClaimSet`, `scored_chunks`, `paper`
- **Outputs**: 8 core metrics, score explanations, `overall_score`
- **Invariants**: Metrics bounded in $[0, 100]$, overall score matches exact weighted sum formula minus penalty:
  $$\text{overall\_score} = \text{clamp}\left(\sum w_i M_i - 0.10 \times \text{hallucination\_score}, 0, 100\right)$$

### Stage 6: Regression & Acceptance Validation Stage (`AcceptanceValidationStage`)
- **File**: `eval/stages/acceptance_validation_stage.py`
- **Purpose**: Evaluates system acceptance gates before report generation:
  1. All upstream stage invariant checks passed cleanly.
  2. Stage serialization succeeded for all upstream stages.
  3. Retrieval diagnostics satisfy minimum thresholds (`gold_retrieved == True`).
  4. Metric range bounds satisfy Stage 0 gold reference expectations.
- **Outputs**: `AcceptanceStatus` (`ACCEPTED` or `REJECTED`), list of gate failures.

### Stage 7: Report Generation Stage (`ReportGenerationStage`)
- **File**: `eval/stages/report_generation_stage.py`
- **Purpose**: Assembles `QuestionReport` dataclass, populates pipeline stage traces, and formats markdown audit reports displaying system acceptance status.
- **Inputs**: All Stage 0–6 outputs, metrics, and acceptance status
- **Outputs**: `QuestionReport` instance

---

## 2. Artifact Provenance Versioning & Replay

All stage inputs, outputs, runtimes, invariant check results, and system provenance metadata are automatically saved to disk:
`eval/artifacts/<question_id>/stage_<N>_<stage_name>.json`

Each artifact contains full provenance versioning metadata:
```json
{
  "provenance": {
    "run_id": "8f3b2a19-...",
    "timestamp": "2026-07-22T17:50:38Z",
    "git_commit": "e4a2c1f",
    "embedding_model": "all-MiniLM-L6-v2",
    "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "llm_model": "qwen2.5:3b-instruct",
    "config_hash": "a91f3e...",
    "dataset_version": "v1.0"
  }
}
```

---

## 3. Verification & Testing Commands

### Run Automated Unit Test Suite
```bash
python -m unittest eval/test_stage_invariants.py
```

### Run Stage Validation Harness CLI
```bash
python eval/stage_harness.py --stage gold_reference --question-id Q1
python eval/stage_harness.py --stage retrieval --question-id Q1
python eval/stage_harness.py --stage reranker --question-id Q1
python eval/stage_harness.py --stage claim_extraction --question-id Q1
python eval/stage_harness.py --stage acceptance_validation --question-id Q1
```

### Run Regression Testing with Tolerances
```bash
python eval/regression_tester.py --current eval/results/latest_run.json --baseline eval/results/baseline_gold.json --noise-tolerance 1.0 --critical-tolerance 5.0
```
