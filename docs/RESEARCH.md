# Research protocol (pre-registered before evaluation)

## Research question

On QASPER's paper-level evidence retrieval task, does a lightweight structure-aware candidate-selection step improve retrieval of annotator-provided evidence compared with BM25, dense retrieval, and reciprocal-rank fusion, especially for questions whose gold evidence is in a table or figure? This is a retrieval study, not a claim that a complete QA system is more accurate or safer.

## Motivation and base benchmark

QASPER was introduced to measure information-seeking QA over complete NLP papers and provides supporting evidence annotations. The benchmark card identifies CC BY 4.0 and an official train/validation/test split. We use its paper-level splits rather than the repository's old hand-authored QA artifacts. See the dataset card and verified bibliographic reference in `references.bib`.

Problem statement: scientific-paper QA depends on finding the source passages that support an answer. A retrieval system can fail even if its answer generator is capable, and evidence passages may be structurally different (ordinary prose, table/caption content, or figure/caption content). We will test whether a generic structural signal helps recover annotated evidence, holding the paper, query, chunking, corpus, and retrieval cutoff fixed.

## Harness choice and legacy evaluation disagreement

The sole research harness is `eval/qasper_study.py`; `scripts/reproduce.py` wraps it and derives the failure report and paper tables from the same raw run. The historical acceptance harness used regex/keyword checks authored around known system behavior after fixes. It checked answer form and selected terms, not evidence entailment, and could award a pass to factually incorrect statements. Other old evaluators differed in their paper/query inputs, prompt path, output parsing, pass thresholds, and metrics, so their scores did not estimate a shared target. They are removed or retained only as regression/history artifacts and are excluded from this paper. The current study uses one frozen dataset release, one paper-local evidence mapping, and one set of ranking metrics for every condition.

## Hypotheses and falsification

- H1: structure-aware selection increases evidence Recall@10 on the predeclared table/figure subset relative to B4 (hybrid + cross-encoder + MMR), with a paired bootstrap 95% confidence interval for the Recall@10 difference excluding zero.
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

Planned retrieval conditions, with identical per-paper candidate corpus and cutoff: (B0) BM25; (B1) dense retrieval with one fixed embedding checkpoint; (B2) reciprocal-rank fusion of B0 and B1; (B3) B2 followed by one fixed cross-encoder; (B4) B3 followed by maximal marginal relevance; (B5) B4 plus generic structure-aware selection. The fixed embedding checkpoint is `intfloat/e5-small-v2` at `ffb93f3bd4047442299a41ebb6fa998a38507c52`; the reranker is `cross-encoder/ms-marco-MiniLM-L-6-v2` at `233902d25c440f23af6f7d6e94d2946bac0bee0a`. Candidate units are QASPER source paragraphs and figure/table captions (the dataset is already parsed, so PDF parsing is not under test). The candidate pool is top 40 by RRF, final cutoff is 10, MMR lambda is 0.7, and RRF constant is 60. The structural condition applies the repository generic question-type/chunk-type score with a fixed 0.25 weight over the MMR rank score. B0 is BM25 in this retrieval-only study; a no-retrieval generator condition is excluded because answer generation is outside the registered question. No chunk-size tuning occurs because source paragraphs are the gold evidence unit. The code commit, evaluator SHA-256, configuration hash, dataset hash, CPU runtime, and model revisions are written to every run record. If a model cannot be downloaded or run on CPU, that condition is marked NOT VERIFIED and is not silently replaced.

Retrieval is restricted to the question's source paper, as required by QASPER's task. Gold evidence is mapped to source paragraph IDs before ranking. No answer generation or LLM judge is part of the primary experiment.

## Outcomes and analysis

Primary outcome: Recall@10 of gold evidence paragraphs on the gold-referenced table/figure subset, with per-query paired bootstrap 95% confidence interval for B5 minus B4. Secondary outcomes: overall evidence Recall@5/10, MRR, nDCG@10; answerability-stratified retrieval; per-evidence-type retrieval; latency and peak process memory where measured. A retriever returns ranked chunk IDs; evidence recall counts any annotated evidence unit retrieved, and the exact matching rules are frozen in the evaluator and unit tests before test scoring.

Use 10,000 fixed-seed paired bootstrap resamples over test questions and a 10,000-resample paired sign-randomization test; report absolute differences, percentile confidence intervals, p-values, and the number of questions. H1 compares B5 with B4 on questions whose gold evidence references a table or figure. H2 checks whether the lower confidence bound for overall Recall@10 difference (B5 minus B4) is greater than -0.02. As a secondary analysis, report paired overall Recall@10 differences for every condition pair with Holm-adjusted p-values; these exploratory comparisons do not replace H1/H2. Report all conditions and missingness. No significance claim is made if a test is not run or an interval crosses zero.

## Scope limits

This benchmark is NLP-focused; it does not establish general performance across scientific fields. Dataset evidence annotations can be incomplete and paragraph-level. QASPER is not a test of equation parsing, multi-paper comparison, citation correctness in generated answers, human-judge agreement, or end-to-end abstention calibration. Those claims are excluded unless a separate audited dataset and protocol are completed. The project will not claim novelty from combining standard retrievers. Contribution, if supported, is a controlled analysis of generic structure-aware evidence retrieval and its failure modes under a reproducible CPU setup.
