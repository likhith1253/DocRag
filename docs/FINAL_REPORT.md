# Final research and engineering report

## Project outcome

DocRag now has a registered, reproducible multimodal evidence-selection study intended as a serious research portfolio and preprint draft. The research question is whether quote-level retrieval recall adequately represents retrieval of a complete annotated evidence set when questions require multiple text and visual evidence units. The earlier QASPER structural-retrieval study remains a separately reported negative precursor and is not pooled into the lead results.

This is not a guarantee of Q1 journal acceptance. The present evidence is benchmark-based and limited to fixed candidate pools. A stronger journal submission would benefit from independent human-audited evidence annotations and replication beyond the supplied candidates.

## Held-out results

All results below were produced by the frozen evaluator at commit `ce84d1a5fde675f9614e5cb0c49f8b78a9c7c73a`, with protocol SHA-256 `886462ae787a7bee7567ae94c36fd838bf7afb79c54bd34c9aad968328ad0f87` and evaluator SHA-256 `e1f43fda2ea44eec80e84fc46418743595d3c2cee6b57ecd04cbe98822e91332`.

- On MMDocRAG, the mean per-question gap between quote Recall@10 and complete-evidence coverage was **0.345** on cross-modal questions (95% paired bootstrap CI **[0.327, 0.363]**, sign-randomization **p=0.00009999**, **n=1,237**). Across all 2,000 answerable test examples, the gap was **0.229** (95% CI **[0.216, 0.242]**).
- The gap was **0.305** larger for cross-modal than single-modality MMDocRAG questions (95% stratified bootstrap CI **[0.284, 0.325]**, label-permutation **p=0.00009999**, n=1,237 and 763).
- Score calibration did not reliably change MMDocRAG cross-modal complete-evidence coverage versus global BM25: **+0.008** (95% CI **[-0.009, 0.026]**, Holm-adjusted **p=0.701**). Equal quotas had a **-0.012** difference (95% CI **[-0.031, 0.006]**, Holm-adjusted **p=0.701**). The study does not support a general selector improvement claim.
- The strict SPIQA test-B rule retained **73 of 228** questions and excluded **155** because all textual contexts and visual references could not be aligned to released candidates. On the retained subset, the mean gap was **0.432** (95% CI **[0.378, 0.485]**). Equal quotas increased complete coverage by **0.219** over global BM25 (95% CI **[0.123, 0.315]**, Holm-adjusted **p=0.00050**). This is limited transfer evidence with a small, selected denominator.
- At k=10, global BM25 fully retrieved the annotated set for 528/1,237 MMDocRAG cross-modal questions, partially retrieved it for 701, and retrieved none for eight. On the aligned SPIQA subset the corresponding counts were 8, 62, and three.

Raw source outputs: [MMDocRAG test](../results/20261110T142142Z_mmdocrag_test_6658f770325d/raw.json), [SPIQA test-B](../results/20261110T142218Z_spiqa_test_39e8fba05c7f/raw.json), and [dataset statistics](../results/20261110T142352Z_multimodal_dataset_stats_985534d2cbd2/dataset_stats.json). Generated artifacts are in `paper/generated/`.

These are retrieval metrics. A positive evidence-sufficiency gap does not establish that a generated answer is wrong; a selected subset may contain sufficient alternative evidence, and model parametric knowledge is outside this experiment.

## Study and provenance

- Base studies: SPIQA (NeurIPS 2024) and MMDocRAG (NeurIPS 2025), both verified against official NeurIPS proceedings. References are in `references.bib`.
- Data revisions, license notices, file sizes, SHA-256 hashes, protocol hash, and evaluator hash are frozen in `data/frozen/multimodal_manifest.json`.
- Development runs used MMDocRAG dev and SPIQA validation. Both held-out sets were evaluated once after commit `ce84d1a` with a clean worktree and the frozen hash checks.
- Primary computation ran on CPU under Windows 11, Python 3.12.5, on an Intel processor with 16 logical CPUs. MMDocRAG evaluation took 32.9 seconds; SPIQA transfer analysis took 10.8 seconds. No hosted GPU, paid API, or remote machine was used.
- The official MMDocRAG source notice is CC BY-NC 4.0; SPIQA is CC BY 4.0. Source data files are local and excluded from Git. Raw result files contain IDs, rankings, metrics, and provenance, not candidate text.

## What changed

- Registered a new lead study on complete evidence-set coverage and a strict cross-benchmark transfer rule in `docs/RESEARCH_V2.md`.
- Added a fail-closed evaluator for BM25 global ranking, modality quotas, score calibration, text-only, image-only, and gold-modality allocation conditions.
- Added pinned benchmark downloads, integrity checking, dataset statistics, per-question raw results, paired inference, failure analysis, and paper artifact generation.
- Rewrote the README and preprint draft to match evidence. Archived the previous QASPER generated tables under `paper/archive/qasper/` and retained its raw outputs as a distinct historical study.
- Added matplotlib as a locked development dependency to produce the paper figure. Updated CI lint coverage for the new core study scripts and tests.

## Verification

- Fast tests: **136 passed, 87 deselected, 24 subtests passed**.
- Ruff: all curated application, evaluator, and study files passed.
- Mypy: success on four configured source files.
- `uv sync --locked --group dev`: success.
- `uv build`: source distribution and wheel built successfully.
- Both frozen test runs passed evaluator, source-hash, clean-worktree, and protocol-hash guards.
- `uv run python scripts/reproduce_multimodal.py` regenerated result tables, policy tests, failure counts, and the PNG figure from raw test outputs.
- The application CPU health and generation smoke checks belong to the earlier engineering phase; they do not support answer-quality claims in this paper.

## What did not work or remains limited

- Within-modality score calibration did not reliably improve complete evidence coverage on MMDocRAG.
- Equal modality quotas helped on the small aligned SPIQA subset but not on MMDocRAG; this dataset difference blocks a general recommendation.
- Strict SPIQA text-context alignment excluded most of test-B. The alignment rule is frozen and exclusions are retained; they were not repaired after viewing test outcomes.
- The exact-set metric assumes supplied gold units are complete and jointly required. It may penalize redundant or incomplete annotations and is not a direct answer-quality measure.
- No answer generation, judge agreement, human grading, citation precision, abstention calibration, raw pixel model, PDF parser comparison, or unrestricted-corpus retrieval was evaluated.

## NOT VERIFIED and exact user commands

- **LaTeX PDF build:** `latexmk` is unavailable in this environment. Install a TeX distribution and run from `paper/`: `latexmk -pdf main.tex`.
- **V100 generation/OOM path:** no V100 access was available. On the university Slurm cluster, run `sbatch hpc/verify_v100_generation.sbatch`; submit both logs and outputs for analysis. Any conclusion about V100 behavior remains NOT VERIFIED.
- **Docker build/runtime:** Docker Desktop's Linux engine was unavailable. Start Docker, then run `docker build -t docrag-research:local .` and `docker run --rm -p 9001:9001 -v docrag-data:/data docrag-research:local`; check `http://127.0.0.1:9001/health` and persistence.
- **Direct comparison with OpenScholar, HQDR, or other trained systems:** not reproduced. Their published scores are not compared with these results.
- **Source-code redistribution license:** the repository still has no `LICENSE`. Ownership and license choice require the owner's review.
- **End-to-end answer quality and human agreement:** not part of this registered study and not verified.

## Actions reserved for the project owner

- Personally verify every manuscript claim, value, and reference against the cited primary source and raw files. The status note in `paper/STATUS.md` warns that unchecked AI-generated material or references can cause serious consequences, including an arXiv submission ban.
- Add accurate author names, affiliations, contributions, acknowledgments, and disclosures; confirm licensing and author rights.
- Decide whether the evidence is strong enough for a preprint, choose an appropriate venue, obtain any required arXiv endorsement, and personally submit. Q1 classification or acceptance cannot be guaranteed.
- Resolve repository code ownership/licensing before public redistribution.
- Human answer grading was not collected and is not needed for the reported retrieval question. Any generated-answer study requires a separate frozen protocol and real human labels.
