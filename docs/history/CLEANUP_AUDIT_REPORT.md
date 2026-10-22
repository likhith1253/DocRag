# Cleanup Audit Report

Date: 2026-08-06

Scope: repository-wide search for benchmark/evaluation entry points, direct orchestrator callers, and ad hoc debug scripts.

## Unused Files

These files do not appear to be part of the production API path and are not referenced by active production code.

- `run_http_benchmark.py`
- `scripts/verify_50_runs.py`
- `scripts/run_hpc_verification.py`
- `scripts/retrieval_audit.py`
- `scripts/run_and_print_audit.py`

## Duplicate Scripts

These scripts overlap heavily in purpose and all bypass the production HTTP API by calling internal orchestrator logic or by replaying ad hoc benchmark flows.

- `scripts/verify_50_runs.py`
- `scripts/run_hpc_verification.py`
- `scripts/retrieval_audit.py`
- `scripts/run_and_print_audit.py`
- `run_http_benchmark.py`

## Legacy Tests

These are still useful as regression coverage, but they are legacy benchmark/evaluation style tests rather than the desired production HTTP benchmark path.

- `tests/test_orchestrator.py`
- `tests/test_manual_queries.py`
- `tests/test_one_query_timings.py`
- `tests/test_large_integration.py`
- `tests/test_e2e_retrieval.py`
- `tests/test_escalated_e2e.py`

## Temporary Debug Scripts

These scripts are diagnostic or forensic in nature and should not be treated as the production evaluation runner.

- `scripts/deep_pipeline_audit.py`
- `scripts/run_and_print_audit.py`
- `scripts/retrieval_audit.py`
- `scripts/run_hpc_verification.py`
- `scripts/verify_50_runs.py`
- `scripts/test_20_runs.py`
- `scripts/run_final_validation.py`

## Recommended Removals

Safe to remove after the new production API benchmark runner is in place and shell wrappers are updated:

- `run_http_benchmark.py`
- `scripts/verify_50_runs.py`
- `scripts/run_hpc_verification.py`
- `scripts/retrieval_audit.py`
- `scripts/run_and_print_audit.py`

## Reasons

- They duplicate the same evaluation intent with different orchestration styles.
- They bypass the production `/query` API path and call internal code directly.
- They create benchmark fragmentation and increase the chance that people run the wrong harness.
- They make it harder to reason about which outputs are authoritative.

## Notes

- I did not remove anything in this audit step.
- Production tests under `tests/` were preserved.
- The canonical benchmark runner should be a single API-based entry point that drives `GET /health` and `POST /query` only.
