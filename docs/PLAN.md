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
- [ ] Establish package layout, pinned Python/dependencies, typed config, install and task commands.
- [ ] Remove paper-specific prompt/retrieval rules; retain and test repository/paper isolation.
- [ ] Retire or update stale tests with a written reason; establish deterministic fast tests and separate slow/GPU markers.
- [ ] Add CI lint and fast tests; audit hidden failures and core typing.

## Phase 3 — evaluation and research design
- [ ] Select and justify one evaluation harness; explain why legacy evaluations differed.
- [ ] Specify the research question and falsification criteria before test exposure.
- [ ] Verify benchmark provenance and licensing; create source-backed in-domain annotations and freeze test hash before tuning.
- [ ] Implement content-addressed generation/judge cache and resumable backend interface.
- [ ] Implement retrieval baselines and ablations under identical conditions; run CPU retrieval metrics.
- [ ] Run feasible generation only on the frozen set or a predeclared subset; preserve raw outputs with run metadata.

## Phase 4 — analysis and release artifacts
- [ ] Compute metrics, uncertainty, paired tests, and failure taxonomy from raw outputs only.
- [ ] Prepare reproducibility scripts, hardware-specific instructions, model/data cards, and user grading template.
- [ ] Write README, final report, and claim-audited paper draft with verified references only.
- [ ] Run the full available CPU reproduction and record every unavailable item as NOT VERIFIED with exact commands.
- [ ] Scan repository/history for secrets before any authorized push.

