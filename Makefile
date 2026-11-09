.PHONY: setup test test-all lint typecheck

setup:
	uv sync --locked --group dev

test:
	uv run pytest -q -m "not slow and not gpu"

test-all:
	uv run pytest -q

lint:
	uv run ruff check settings.py llm/cache.py retrieval/query_analyzer.py retrieval/paper_matcher.py

typecheck:
	uv run mypy

