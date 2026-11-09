# Research protocol (pre-registered before evaluation)

## Research question

On QASPER's paper-level evidence retrieval task, does a lightweight structure-aware candidate-selection step improve retrieval of annotator-provided evidence compared with BM25, dense retrieval, and reciprocal-rank fusion, especially for questions whose gold evidence is in a table or figure? This is a retrieval study, not a claim that a complete QA system is more accurate or safer.

## Motivation and base benchmark

QASPER was introduced to measure information-seeking QA over complete NLP papers. Its authors report 5,049 questions over 1,585 papers and provide supporting evidence annotations. The benchmark card identifies CC BY 4.0 and an official train/validation/test split. We use its paper-level splits rather than the repository's old hand-authored QA artifacts. See the dataset card and verified bibliographic reference in `references.bib`.

Problem statement: scientific-paper QA depends on finding the source passages that support an answer. A retrieval system can fail even if its answer generator is capable, and evidence passages may be structurally different (ordinary prose, table/caption content, or figure/caption content). We will test whether a generic structural signal helps recover annotated evidence, holding the paper, query, chunking, corpus, and retrieval cutoff fixed.

## Hypotheses and falsification

- H1: structure-aware selection increases evidence Recall@10 on the predeclared table/figure subset relative to the strongest non-structural retrieval baseline, with a paired bootstrap 95% confidence interval for the difference excluding zero.
- H2: it does not reduce overall Recall@10 by more than 0.02 absolute (non-inferiority margin, declared before scoring).
- Falsification: H1 fails if the interval includes zero or the point estimate is non-positive. H2 fails if the estimated overall loss exceeds 0.02. We will report either failure and all tested variants.

These are hypotheses, not results. No test examples or scores have been inspected.

## Data and split freeze

Source: `allenai/qasper`, dataset revision `4d9336e735cf4e9e99e8a4d738847703a43512fa`. Revision and source file byte sizes/SHA-256 hashes are frozen in `data/frozen/qasper_manifest.json`. Downloaded parquet files live under ignored `data/downloads/qasper/`; the tracked manifest, not a manually edited copy of examples, defines the immutable source.

- Development: official `validation` split only. Use it for implementation checks and any parameter choice.
- Final test: official `test` split only. Do not use it for tuning, prompt edits, threshold choices, or example-driven changes. Run once after dev choices are fixed; retain all outputs.
- Training: official `train` split is not used for fitting in this retrieval-only study.

The upstream files are frozen before any result computation. If an upstream source changes, it is a new dataset version and requires a new protocol and test freeze.

## Conditions and controls

Planned retrieval conditions, with identical per-paper candidate corpus and cutoff: (B0) BM25; (B1) dense retrieval with one fixed embedding checkpoint; (B2) reciprocal-rank fusion of B0 and B1; (B3) B2 followed by one fixed cross-encoder; (B4) B3 followed by maximal marginal relevance; (B5) B4 plus generic structure-aware selection. The exact model revisions, chunk size, overlap, candidate depth, seed, and code commit must be written to run metadata before the test run. If a model cannot be downloaded or run on CPU, that condition is marked NOT VERIFIED and is not silently replaced.

Retrieval is restricted to the question's source paper, as required by QASPER's task. Gold evidence is mapped to source paragraph IDs before ranking. No answer generation or LLM judge is part of the primary experiment.

## Outcomes and analysis

Primary outcome: Recall@10 of gold evidence paragraphs on the gold-typed table/figure subset, with per-query paired bootstrap 95% confidence interval against the strongest baseline selected on validation. Secondary outcomes: overall evidence Recall@5/10, MRR, nDCG@10; answerability-stratified retrieval; per-evidence-type retrieval; latency and peak process memory where measured. A retriever returns ranked chunk IDs; evidence recall counts any annotated evidence unit retrieved, and the exact matching rules are frozen in the evaluator and unit tests before test scoring.

Use a fixed-seed paired bootstrap over test questions and a paired randomization test; report absolute differences, confidence intervals, p-values, and the number of questions. Report all conditions and missingness. No significance claim is made if a test is not run or an interval crosses zero.

## Scope limits

This benchmark is NLP-focused; it does not establish general performance across scientific fields. Dataset evidence annotations can be incomplete and paragraph-level. QASPER is not a test of equation parsing, multi-paper comparison, citation correctness in generated answers, human-judge agreement, or end-to-end abstention calibration. Those claims are excluded unless a separate audited dataset and protocol are completed. The project will not claim novelty from combining standard retrievers. Contribution, if supported, is a controlled analysis of generic structure-aware evidence retrieval and its failure modes under a reproducible CPU setup.
