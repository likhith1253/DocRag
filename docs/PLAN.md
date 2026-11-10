# Work plan

## Phase 5 — stronger multimodal evidence-selection study (active)
- [x] Freeze MMDocRAG and SPIQA source revisions, hashes, and license/provenance manifest before metrics.
- [x] Implement adapters and exact gold-ID alignment checks; SPIQA test-B requires complete text/figure mapping.
- [x] Implement BM25 global, equal-modality quotas, score calibration, modality-only policies, and a gold-modality allocation reference.
- [ ] Complete dev analysis; commit frozen evaluator/protocol hashes before held-out evaluation.
- [ ] Run MMDocRAG evaluation and SPIQA test-B once; save raw rankings and all derived outputs with config hashes and commit provenance.
- [ ] Update paper, results tables, failure analysis, reproducibility guide, and final report to lead with supported v2 findings while preserving the prior QASPER result as a negative precursor.
- [ ] Verify test suite, lint, paper build if available, repository license notices, and clean Git history; push the completed branch.

## Phase 1 — audit and cleanup (must be a separate commit)
- [x] Confirm checkout and create `research-overhaul` from `main`.
- [x] Inventory architecture, duplicate harnesses, generated artifacts, and broad exception handling.
- [x] Attempt baseline test collection and fix the local pytest plugin mismatch.
- [x] Remove code-RAG-only code and its test consumers; preserve the paper-QA path.
- [x] Untrack historical results and unlicensed sample PDFs while preserving local copies and gold material.
- [x] Record cleanup and decisions; verify imports and collect the remaining tests.
- [x] Run the retained deterministic tests and commit phase 1 separately.

## Phase 2 — reproducible application core
- [x] Establish package metadata, Python 3.12.5 pin, locked CPU-PyTorch dependencies, install and task commands (wheel build and locked sync succeeded).
- [x] Add a typed settings object with nested environment overrides and central paths/collection names.
- [x] Remove paper-name aliases and prompt/retrieval correction rules; add generic evidence patterns and maintain isolation tests.
- [x] Add content-addressed LLM output caching keyed by model, prompt, decoding settings, and seed; make errors distinct from evidence refusals.
- [x] Apply a conservative prompt-token budget using the configured context cap.
- [x] Remove paper-specific prompt/retrieval rules; production core grep finds no named benchmark-paper rules, and isolation tests remain.
- [x] Retire stale one-off tests with a written reason; classify model/storage integration tests as slow and GPU tests separately.
- [x] Add CI lint and fast-test workflow plus scoped mypy; lint and typecheck passed.
- [x] Establish a deterministic fast test suite; collection completes and slow/GPU tests are separately marked.

## Phase 3 — evaluation and research design
- [x] Select the QASPER retrieval-only harness; legacy regex acceptance and HTTP QA scores were self-referential, disagreed on inputs/metrics, and are excluded. The duplicate HTTP harness is removed.
- [x] Specify research question, hypotheses, outcomes, controls, and falsification criteria before test exposure.
- [x] Verify QASPER provenance/license and freeze official splits by revision and SHA-256 before tuning.
- [x] Narrow the primary contribution to evidence retrieval. Generation, LLM judging, and human answer grading are explicitly outside this study; application generation cache remains tested separately.
- [x] Implement BM25/dense/RRF/reranker/MMR/structure conditions with identical source paragraph units, persistent embedding cache, paired inference, per-question rankings, and retrieval failure analysis; unit tests cover metrics, inference, test-split guard, and generated tables.
- [x] Finish the current full CPU validation development run (1,005 questions; exploratory output retained with a dirty-worktree flag). Repeat after the harness is committed so final validation provenance is clean and complete.
- [x] Freeze implementation/protocol commit `d25cd332a442d80f0f44edbda2ec84a09fe0d546`, pin evaluator SHA in manifest, and run the full frozen test once on CPU. No system tuning followed test exposure.
- [x] Decide not to run QASPER generation or judge: primary research question is retrieval-only, and no answer-generation claim will be made.

## Phase 4 — analysis and release artifacts
- [x] Compute final metrics, uncertainty, paired tests, and failure taxonomy from the frozen test raw output only.
- [x] Prepare reproducibility commands, hardware-specific instructions, data/model card, and exact user verification steps.
- [x] Write README, final report, and claim-audited paper draft with verified references only.
- [x] Run the full available CPU reproduction and record every unavailable item as NOT VERIFIED with exact commands.
- [x] Scan repository history for high-confidence credential/private-key patterns before the final authorized push; no matches were found.

