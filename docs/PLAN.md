# Work plan

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
- [ ] Freeze implementation/protocol commit, then run the full frozen test once on CPU. Do not tune the system from test outcomes.
- [x] Decide not to run QASPER generation or judge: primary research question is retrieval-only, and no answer-generation claim will be made.

## Phase 4 — analysis and release artifacts
- [ ] Compute final metrics, uncertainty, paired tests, and failure taxonomy from the frozen test raw output only.
- [ ] Prepare reproducibility commands, hardware-specific instructions, data/model card, and exact user verification steps. (partial)
- [ ] Write README, final report, and claim-audited paper draft with verified references only.
- [ ] Run the full available CPU reproduction and record every unavailable item as NOT VERIFIED with exact commands.
- [ ] Scan repository/history for secrets before any authorized push.

