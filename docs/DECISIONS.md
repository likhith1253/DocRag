# Decisions

- **Starting point:** Use `main` at `718b33c` because the task explicitly requires a new branch from main. Do not import work from the prior local overhaul branch without auditing its diff.
- **Workspace spelling:** The runner exposes this repository as `D:\DocRag`; the provided `D:\Document_RAG` spelling is unavailable. Repository contents confirm the intended project.
- **PDF preservation:** Move PDFs whose terms are not yet checked into ignored local `data/source_papers_unverified/` instead of deleting the only local copies. Do not use them as a public benchmark or redistribute them until license review.
- **Gold preservation:** Keep historical question/answer JSON under `data/legacy_annotations/`. Treat all entries as unverified annotations and exclude them from tuning/evaluation until source evidence and split hygiene are audited.
- **Old results:** Retain them locally but untrack/ignore them. They are not scientific evidence for this work.
- **Test environment:** Initial installed pytest/plugin versions were incompatible. Updated the user-level Python environment to pytest 9.2.0 and pytest-asyncio 1.4.1.post1 to diagnose collection; repository dependency pinning remains future work. The tests must be rerun from a clean locked install.
- **Evaluation harness:** Keep only the paper-QA HTTP harness and its helper temporarily. It will be replaced/extended once the system core and research protocol are ready.
- **GPU:** Do not use remote compute absent a need and explicit authorization. No V100 testing is possible from this workspace; report it as NOT VERIFIED.
- **Bibliography and data:** Add no paper references or public benchmark claims until existence, provenance, and license are verified from authoritative sources.

- **Claim checker scope:** Replace paper-specific semantic rewrites with a generic high-risk number/equation scan. It does not establish semantic entailment or verify every claim; expose it as a risk scan and do not describe a clean scan as a proven claim-verification result.
- **Generation cache:** Use content-addressed per-call cache files keyed by model identifier, full prompt, decoding configuration (including seed), and answer depth. Generation errors propagate as generation errors; cache reads/writes are visible failures. `DOCRAG_FORCE_GENERATION=1` is the explicit bypass.
- **Prompt budget:** Reserve configured generation tokens from `prompt_token_budget` and enforce the remaining approximate token budget as a conservative context character cap. This is an approximation, not tokenizer-exact enforcement.
- **Remote compute and APIs:** No authorization request is needed for current CPU code work; no remote login, paid API, or GPU service has been used. Avoid those unless later evidence shows CPU work cannot meet the planned study.
- **Local registry:** Preserve the local `registry.json` because it contains pre-existing repository metadata; untrack it so neither user metadata nor test-generated records enter Git.

- **CPU dependency lock:** Pin Torch to the official PyTorch CPU index and export the runtime requirements from `uv.lock`; avoid CUDA wheel downloads on laptop installs.
- **Fast test scope:** Tests that initialize real embedding/vector-store models or invoke generation are marked `slow`. Broad test collection currently stalls before output despite targeted fast tests passing, so the fast suite is not yet declared green.
- **Evaluation command:** Removed the premature `make reproduce` target because no canonical reproduction harness exists yet; it will return only when it runs real saved experiments.

- **Primary study scope:** Limit the primary claim to QASPER evidence retrieval and generic structural selection. The repository lacks audited equation/figure annotations and reliable human answer grades; end-to-end generation/claim-verification claims would not be defensible.
- **Test freeze:** Freeze official QASPER test data by upstream revision plus local SHA-256 and byte size before inspecting any examples or computing results. Only validation may guide implementation choices.
