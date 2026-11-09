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
