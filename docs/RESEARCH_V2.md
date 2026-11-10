# Research protocol v2: when does retrieved context contain enough evidence?

## Status and scope

This is the new primary study, replacing the QASPER structure-ranking project as the lead paper. The old QASPER result remains an auditable negative precursor and is not pooled with v2. The new study evaluates evidence selection from fixed candidate pools. It does not evaluate raw-pixel perception, PDF parsing, answer generation, or factuality of generated answers; it must not be called an end-to-end multimodal RAG evaluation.

## Problem statement and research questions

Retrieval evaluations often report the fraction of gold quotes retrieved. But a question may require several evidence units, potentially across text and images. Retrieving most of those units can score well on quote-level Recall@k while leaving the selected context unable to support a complete answer. We ask:

- **RQ1:** Under a fixed quote budget, how large is the gap between micro evidence Recall@k and exact complete-evidence-set coverage?
- **RQ2:** Is that gap larger for questions requiring both textual and visual evidence than for single-modality questions?
- **RQ3:** Do common modality-selection policies change evidence completeness relative to global BM25 ranking, and does the observed pattern transfer from general documents to scientific-paper questions?

The motivation is measurement validity and context sufficiency, not a claim that one heuristic is a new retrieval model. Development showed no advantage for score calibration, so calibration is retained as an exploratory policy rather than the claimed contribution. No held-out result has been inspected.

## Base studies and motivation

1. SPIQA (Pramanick, Chellappa, and Venugopalan, NeurIPS 2024 Datasets and Benchmarks) introduces scientific-paper QA involving figures, tables, and text. Its test-B questions are human-written QASA items. The official dataset card marks it CC BY 4.0.
2. MMDocRAG (Dong et al., NeurIPS 2025 Datasets and Benchmarks) provides fixed candidate quote pools with text and image descriptions, multi-evidence labels, and a held-out evaluation split. The official repository marks data and code CC BY-NC 4.0. It is used only for non-commercial research; raw source data is not redistributed.

Dataset statistics are generated and saved by `scripts/multimodal_dataset_stats.py`; they are not hand-entered into the results narrative. The benchmarks have different units and annotation procedures and are reported separately. MMDocRAG dev is used for implementation checks. SPIQA validation is used only to test the caption adapter. No test split is used for parameter choices.

## Frozen data and leakage controls

- MMDocRAG: `MMDocIR/MMDocRAG`, revision `04b58dbc5c6c4955291124eed411b09114728061`, with `dev_20.jsonl` for development and `evaluation_20.jsonl` for test.
- SPIQA: `google/spiqa`, revision `1774b71511f029b82089a069d75328f25fbf0705`, with `train_val/SPIQA_val.json` for adapter checks and `test-B/SPIQA_testB.json` for external scientific-paper evaluation.
- `data/frozen/multimodal_manifest.json` records source revisions, file byte sizes, and SHA-256 hashes. Downloaded files are ignored by Git and verified before use.
- Before protocol freeze, one MMDocRAG evaluation record and one SPIQA test-B record were inspected only to identify the public JSON schemas. No test metric or outcome was calculated, and no policy setting was chosen from those records. This limited inspection is explicitly disclosed.
- Run the full MMDocRAG dev split to debug the evaluator and select no test-informed parameter. Commit the final protocol, evaluator, and manifest before running either held-out set. Each test is run once. Test errors are reported; no post-test tuning is allowed.

## Systems and controls

The MMDocRAG candidate set is supplied by the benchmark. Image candidates use the benchmark's released image descriptions. The primary base ranker is BM25 over question and candidate text. Candidate text is the provided text quote or image description. This evaluates description-based evidence selection, not visual perception. All methods see identical candidate pools and use the same underlying scores.

Compare global BM25 ranking; equal text/image quotas at each budget (odd slots go to the modality with the higher best raw BM25 score); within-modality robust score calibration followed by global ranking; text-only selection; image-only selection; and an oracle modality-allocation reference using gold modality proportions while retaining BM25 ranking within each modality. The oracle is non-deployable and is not a full oracle retriever. Stable ties follow input order and candidate ID. Budgets are k ∈ {5, 10, 15, 20}; a budget is capped at the number of candidates. Candidate IDs are deduplicated only when identical IDs occur within the same modality; conflicting modality IDs are fatal errors. Duplicate counts are retained in raw output.

The calibration policy uses the within-modality median and 1.4826×median absolute deviation, with mean/std then unit-scale fallback if the scale is zero. It is an exploratory ablation; dev results do not support a benefit claim.

For SPIQA test-B, candidates are all provided text passages and figure/table captions for each paper. Visual evidence IDs come from `referred_figures_tables`. Text evidence contexts are normalized and matched as substrings within candidate passages; if a context occurs multiple times, the shortest containing passage is selected, with input order breaking ties. Include a question only if every provided context maps to a passage and all visual references map to candidate captions. Report exclusions and IDs. The confirmatory transfer subset requires both text and visual gold evidence. The same BM25 and selection policies are applied. No test-specific mapping change is allowed after results.

## Outcomes and inference

The primary outcome is the **evidence sufficiency gap** at k=10 for global BM25: mean per-question quote Recall@10 minus exact complete-evidence-set coverage, restricted to MMDocRAG test questions with both text and image gold evidence. The primary contrast is this per-question gap against zero. The second preregistered contrast is the gap difference between cross-modal and single-modality MMDocRAG test questions. The third is the same gap on the fully aligned cross-modal SPIQA test-B subset, reported as external scientific-paper transfer.

Secondary outcomes include exact complete-evidence-set coverage, micro evidence Recall@k, example-level evidence F1, modality-specific recall, and the coverage gap for every policy and budget. Report both answerable denominator and any unanswerable, duplicate-ID, or unaligned-question counts. The policies' paired completeness differences versus global BM25 are exploratory and Holm-adjusted within each benchmark.

Use paired question-level bootstrap intervals with 10,000 resamples, seed 20261110, and paired sign-randomization tests with 10,000 draws for within-question gap and policy contrasts. For the cross-modal versus single-modality subgroup contrast, use stratified bootstrap and permutation over question labels. Report effect sizes, 95% intervals, p-values, and n. The measurement hypothesis is not supported if the primary gap interval includes zero; the subgroup hypothesis is not supported if its interval includes zero. A measured gap does not by itself prove answer failure; it indicates that quote-level recall is not equivalent to full annotated-evidence coverage.

## Research value and limitations

The potential contribution is a controlled analysis of a metric mismatch between quote-level retrieval and complete evidence-set sufficiency, with a fixed-budget policy comparison and a scientific-paper transfer check. It is not a new multimodal encoder. MMDocRAG uses a fixed candidate pool and precomputed descriptions; SPIQA's scientific-paper test is small, derived from QASA, and relies on caption/reference annotations. The strict text-evidence alignment rule may exclude examples and must be quantified. Neither benchmark establishes answer correctness, citation faithfulness, raw visual understanding, or unrestricted-corpus retrieval. A journal submission would benefit from an independently collected scientific-paper test set and human audit of the evidence mappings; this project will not manufacture those labels.

## Held-out gate

The evaluator refuses test scoring unless the worktree is clean and evaluator/protocol hashes match `data/frozen/multimodal_manifest.json`. Raw outputs contain candidate IDs and rankings rather than copyrighted source text, plus dataset/evaluator/protocol hashes, software and hardware details, config hash, run timestamp, per-question metrics, exclusions, and paired inference. Tables and figures are generated from saved raw results. `make reproduce-v2` verifies saved outputs and reruns the protocol on the frozen local data.
