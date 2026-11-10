# Final research and engineering report

## Project outcome

The repository was refactored into a CPU-first, installable research prototype and evaluated as a retrieval-only study. The registered question was whether a generic structure-aware ordering step adds retrieval value after hybrid retrieval, cross-encoder reranking, and maximal marginal relevance (MMR), especially for QASPER questions whose annotated evidence refers to tables or figures.

The answer is mixed and the primary hypothesis was not supported. On the frozen test table/figure subset, structure-aware ordering over MMR had a paired Recall@10 difference of **+0.0075**, with a 95% paired bootstrap interval of **[-0.0081, 0.0253]**, paired sign-randomization **p=0.4153**, and **n=220**. The interval crosses zero. On all answerable questions whose evidence mapped to source passages, the same contrast was **+0.0181** (95% CI **[0.0113, 0.0254]**, **n=1,272**); this meets the registered overall non-inferiority margin of -0.02. However, plain hybrid plus cross-encoder reranking reached Recall@10 **0.758**, compared with **0.649** for reranking+MMR and **0.668** for MMR+structure. The paired reranking-minus-structure difference was **0.0905** (95% CI **[0.0710, 0.1101]**, Holm-adjusted **p=0.0015**). The evidence therefore does not support replacing the reranker with the MMR-plus-structure sequence.

The primary test result is negative. On validation, the predeclared table/figure contrast was positive, but that development pattern did not generalize to the held-out test. Do not adjust the structure weight, MMR parameters, or test protocol using this result.

## Study and provenance

- Benchmark: QASPER, pinned revision `4d9336e735cf4e9e99e8a4d738847703a43512fa`; test file SHA-256 `071f79659d4c60b50dadbcdc9a2db0e1ab29a73c2ac779e94b1aa1991187b07b`.
- Systems: BM25; E5 dense retrieval; BM25+E5 reciprocal-rank fusion; hybrid plus cross-encoder; hybrid plus cross-encoder and MMR; and MMR followed by generic structure-aware ordering.
- Test protocol commit: `26fbcfc14712f3c7d59e4587e88a17be74618c2d`. Evaluator SHA-256: `2f34158c765cef7f8857d031d4519466ebb3d7fb5e55689a039f802c6a119864`.
- Final raw test run: [`results/20261110T125049Z_test_b266b19c27/raw.json`](../results/20261110T125049Z_test_b266b19c27/raw.json). It records a clean worktree at evaluation, configuration SHA-256 `b266b19c27a868af9bb7303fd3d6d7850acec89218a77b4576d5b798e5549e3a`, all six systems, full official test split, pinned models, Python/software versions, CPU hardware, stage times, and raw per-question rankings.
- The full test contained 416 papers and 1,451 questions: 1,372 answerable, 79 unanswerable, 1,272 with mappable evidence, and 100 answerable questions whose evidence did not map to the source paragraphs/captions under the registered exact normalized-containment rule.
- Analysis used 10,000 fixed-seed paired bootstrap resamples, 10,000 paired sign-randomization resamples, and Holm adjustment across the 15 secondary pairwise comparisons.
- QASPER statistics for train/validation are in [`results/dataset_stats/20261110T041622Z_qasper_stats.json`](../results/dataset_stats/20261110T041622Z_qasper_stats.json). Test split counts and mappings come from the test raw run.

## Headline retrieval metrics

All values below are generated from the frozen test raw file. Recall is averaged across the 1,272 answerable questions with at least one mapped evidence passage.

| Condition | Recall@5 | Recall@10 | MRR | nDCG@10 |
|---|---:|---:|---:|---:|
| BM25 | 0.428 | 0.595 | 0.367 | 0.391 |
| E5 dense | 0.558 | 0.723 | 0.486 | 0.507 |
| BM25 + E5 RRF | 0.532 | 0.713 | 0.478 | 0.496 |
| Hybrid + cross-encoder | 0.602 | 0.758 | 0.541 | 0.555 |
| Hybrid + cross-encoder + MMR | 0.475 | 0.649 | 0.456 | 0.457 |
| MMR + structure | 0.495 | 0.668 | 0.450 | 0.460 |

The generated tables are [`paper/generated/main_results.tex`](../paper/generated/main_results.tex) and [`paper/generated/pairwise_comparisons.tex`](../paper/generated/pairwise_comparisons.tex). The latter includes all paired overall Recall@10 contrasts and Holm-adjusted p-values.

## Failure analysis

The registered retrieval taxonomy and examples are in [`failure_analysis.json`](../results/20261110T125049Z_test_b266b19c27/failure_analysis.json). Among the 1,272 answerable questions with mapped evidence, Recall@10 had 329 complete misses for BM25, 193 for dense E5, 205 for RRF hybrid, 151 for cross-encoder reranking, 256 for MMR, and 234 for MMR+structure. There were 100 answerable questions whose annotated evidence could not be mapped; those are reported separately and excluded from ranking metrics. The table/figure-reference subset had 220 questions; MMR+structure missed all mapped evidence at top ten on 42 of them, versus 29 for cross-encoder reranking and 44 for MMR.

The experiment cannot classify PDF parser loss, generation errors, verifier misses, false refusals, or application infrastructure failures: the retrieval study uses QASPER's supplied text and produces no answers. Do not infer these error types from retrieval rankings.

## Compute and efficiency

The final test run executed on a CPU-only Windows 11 machine, Python 3.12.5, Intel Family 6 Model 186, 16 reported logical CPUs, PyTorch `2.15.0+cpu`, Sentence Transformers `5.7.0`, and Transformers `4.57.6`. Total measured evaluator time was **27,268.94 seconds**; model loading was **26.90 seconds**. The measured embedding-cache/encoding stage was **22,290.27 seconds**, cross-encoder scoring **4,919.33 seconds**, MMR selection **45.91 seconds**, and peak sampled process RSS **1,197,953,024 bytes**. The test run encoded new test-corpus passages; subsequent local reproduction can reuse the content-addressed vector cache. These are aggregate cold-run stage totals, not per-query cold/warm latency distributions. No monetary API cost was incurred.

## Baseline literature and scope

QASPER (Dasigi et al., NAACL-HLT 2021) is the evidence-annotated benchmark for this study. The closest recent baseline paper is Huang, Velcin, and Kessaci, “Structure-Aware Quantized Retrieval for Long-Document Question Answering,” Findings of ACL 2026, DOI `10.18653/v1/2026.findings-acl.209`. That paper reports a learned hierarchical and quantized retriever on QASPER, with comparisons against BM25, ColBERT, and dense baselines. HQDR is included in related work but was **not reproduced**; its training and scoring method, dataset mapping, and experimental setup differ, so its reported numbers are not pooled with or directly compared to this paired test. This study tests only the added value of a fixed, training-free structural ordering stage over conventional retrievers.

## Engineering changes and checks

- Removed code-RAG-only modules, obsolete overlapping evaluators, local runtime artifacts, and unlicensed PDFs from version control; retained user-local source files ignored from Git and preserved legacy gold annotations as unverified data.
- Removed paper-specific prompt/retrieval rules, retained paper/repository isolation, added typed central settings and environment overrides, content-addressed generation caching, CPU-first model policy, and explicit failure propagation.
- Added pinned Python/locked dependencies, Make targets, CI configuration, scoped Ruff/mypy checks, a deterministic fast suite, Docker and Slurm instructions, QASPER downloader/manifest, retrieval harness, raw analysis, generated paper tables, and this report.
- Verified locally: `uv sync --locked --group dev`; `uv build`; scoped Ruff and mypy; and fast tests (`131 passed, 87 deselected, 24 subtests passed`). The project verification archive is in `results/verification/` after final checks.
- A high-confidence token/private-key scan covered 1,259 Git blobs across reachable history and found no matches. This is a pattern scan, not a general audit for every form of sensitive information.
- A CPU Qwen2.5-0.5B generation smoke produced `READY`; this is a runtime smoke test, not answer-quality evidence.
- The API was also started with `uv run uvicorn api.main:app --host 127.0.0.1 --port 9001`; a request to `http://127.0.0.1:9001/health` returned `status=ok` and reported the configured Qwen2.5-0.5B backend loaded on CPU. This was a local health smoke only; it does not verify document ingestion plus answer quality end to end.
- The test was run once by `uv run python scripts/reproduce.py --split test --allow-test`; the raw rankings and derived outputs were saved without changing the evaluator or research system after test exposure.

## NOT VERIFIED

- **V100 CUDA generation/OOM diagnostic:** No V100 access was available. From the repository root on the university cluster, run `sbatch hpc/verify_v100_generation.sbatch`. The array job tests eager and SDPA attention separately and saves Slurm logs under `results/`; inspect both runs and submit the resulting files for analysis. GPU memory/error-recovery conclusions remain unverified.
- **Docker image and runtime:** Docker Desktop's Linux engine was unavailable. After starting a working Docker daemon, from the repository root run `docker build -t docrag-research:local .`, then `docker run --rm -p 9001:9001 -v docrag-data:/data docrag-research:local`; verify the API health endpoint and persistent repository state.
- **LaTeX compilation:** `latexmk` is not installed in this environment. Install a TeX distribution with `latexmk`, then run `cd paper` followed by `latexmk -pdf main.tex`. The generated tables exist, but a successful PDF build is not verified.
- **HQDR reproduction:** The 2026 structure-aware QASPER baseline is cited and its official ACL metadata verified, but its code/training and results were not reproduced. Do not claim a direct win over it.
- **Application answer quality, judge agreement, citation faithfulness, calibrated abstention, model-size/quantization parity, remote API behavior, and the reported Qwen2.5-3B V100 failure:** These are outside the registered retrieval study and remain unverified. The CPU generation smoke does not support these claims.
- **Remote CI:** GitHub Actions CI completed successfully for the final pushed commit `c15ff1afb3760d0160bc5c48957e7c6b56fdfa67` ([workflow run](https://github.com/likhith1253/DocRag/actions/runs/42823841150)).
- **Project redistribution license:** The repository contains no `LICENSE`; the owner must determine code ownership and select a license before redistribution. Preserved sample PDFs remain excluded because their terms are not established.

## Actions reserved for the project owner

- Personally verify every paper claim, generated table, and bibliography entry before submission. The draft warns that unchecked AI-generated content or references can have serious consequences, including arXiv submission sanctions.
- Add author names, affiliations, contributions, acknowledgments, and any required disclosures accurately; obtain any required arXiv endorsement and personally submit the paper.
- Resolve the source-code license/ownership and the redistribution terms for any local PDFs before releasing them.
- Human answer grading is not needed for this retrieval-only research question and was not collected. If the study is expanded to generated-answer quality, create a separate frozen protocol and collect real human labels before making such claims.
