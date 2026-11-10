# Contributing

## Environment

Use Python 3.12.5 and `uv sync --locked --group dev`. Do not commit caches, source papers with unclear terms, registry state, local model files, credentials, or result edits made by hand.

## Changes

- Keep application and benchmark behavior independent of named benchmark examples or papers.
- Preserve repository and paper isolation and refusal/error distinctions.
- Add deterministic tests for changed behavior. Mark model-backed and storage integration tests `slow`; GPU-only tests use `gpu`.
- Run `make lint`, `make typecheck`, and `make test` before proposing changes.
- Research changes must use validation data for iteration and preserve the frozen test hash. Record configuration, code commit, model revisions, and raw outputs.
- A benchmark failure is evidence to report, not a reason to tune on the held-out test.

## Data and models

Review source licensing and attribution before adding artifacts. See `docs/DATA_MODEL_CARD.md`.
