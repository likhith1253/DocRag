.PHONY: setup test test-all lint typecheck verify reproduce reproduce-dev

setup:
	uv sync --locked --group dev

test:
	uv run pytest -q -m "not slow and not gpu"

test-all:
	uv run pytest -q

lint:
	uv run ruff check settings.py llm/cache.py retrieval/query_analyzer.py retrieval/paper_matcher.py eval/qasper_study.py eval/failure_analysis.py eval/paper_table.py scripts/dataset_stats.py scripts/download_qasper.py scripts/reproduce.py scripts/smoke_generation.py scripts/verify_cuda_generation.py scripts/verify_project.py tests/test_qasper_study.py

typecheck:
	uv run mypy

verify:
	uv run python scripts/verify_project.py

reproduce:
	uv run python scripts/reproduce.py --split test --allow-test

reproduce-dev:
	uv run python scripts/reproduce.py --split validation

