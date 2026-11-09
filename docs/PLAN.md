# Work plan

## Phase 1 — audit and cleanup (must be a separate commit)
- [x] Confirm checkout and create `research-overhaul` from `main`.
- [x] Inventory architecture, duplicate harnesses, generated artifacts, and broad exception handling.
- [x] Attempt baseline test collection and fix the local pytest plugin mismatch.
- [x] Remove code-RAG-only code and its test consumers; preserve the paper-QA path.
- [x] Untrack historical results and unlicensed sample PDFs while preserving local copies and gold material.
- [x] Record cleanup and decisions; verify imports and collect the remaining tests.
- [x] Run the retained deterministic tests (19 passed) and commit phase 1 separately.

## Phase 2 — reproducible application core
- [x] Establish package metadata, Python 3.12.5 pin, locked CPU-PyTorch dependencies, install and task commands (wheel build and locked sync succeeded).
- [x] Add a typed settings object with nested environment overrides and central paths/collection names.
- [x] Remove paper-name aliases and prompt/retrieval correction rules; add generic evidence patterns and maintain isolation tests.
- [x] Add content-addressed LLM output caching keyed by model, prompt, decoding settings, and seed; make errors distinct from evidence refusals.
- [x] Apply a conservative prompt-token budget using the configured context cap.
- [ ] Remove paper-specific prompt/retrieval rules; retain and test repository/paper isolation.
- [ ] Retire or update stale tests with a written reason; establish deterministic fast tests and separate slow/GPU markers. (ongoing; 84 targeted tests pass)
- [x] Add CI lint and fast-test workflow plus scoped mypy; lint and typecheck passed.
- [ ] Stabilize full fast-suite collection; current broad pytest invocation stalls before reporting tests. Targeted deterministic slice passes (55 tests); heavyweight storage/model cases are being marked slow.

## Phase 3 — evaluation and research design
- [ ] Select one retrieval-only evaluation harness and explain why legacy evaluations differed.
- [x] Specify research question, hypotheses, outcomes, controls, and falsification criteria before test exposure.
- [x] Verify QASPER provenance/license and freeze official splits by revision and SHA-256 before tuning.
- [ ] Primary experiment excludes generation/judging; the application generation cache exists, but a separate judge cache is out of scope unless the scope expands.
- [ ] Implement retrieval baselines and ablations under identical conditions; run CPU retrieval metrics.
- [ ] Run feasible generation only on the frozen set or a predeclared subset; preserve raw outputs with run metadata.

## Phase 4 — analysis and release artifacts
- [ ] Compute metrics, uncertainty, paired tests, and failure taxonomy from raw outputs only.
- [ ] Prepare reproducibility scripts, hardware-specific instructions, model/data cards, and user grading template.
- [ ] Write README, final report, and claim-audited paper draft with verified references only.
- [ ] Run the full available CPU reproduction and record every unavailable item as NOT VERIFIED with exact commands.
- [ ] Scan repository/history for secrets before any authorized push.

