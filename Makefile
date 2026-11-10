.PHONY: setup test test-all lint typecheck verify reproduce reproduce-dev reproduce-qasper reproduce-v2 reproduce-v2-dev run-v2-tests

setup:
	uv sync --locked --group dev

test:
	uv run pytest -q -m "not slow and not gpu"

test-all:
	uv run pytest -q

lint:
	uv run ruff check settings.py llm/cache.py retrieval/query_analyzer.py retrieval/paper_matcher.py eval/qasper_study.py eval/multimodal_selection.py eval/failure_analysis.py eval/paper_table.py scripts/dataset_stats.py scripts/download_qasper.py scripts/reproduce.py scripts/download_multimodal_benchmarks.py scripts/multimodal_dataset_stats.py scripts/reproduce_multimodal.py scripts/smoke_generation.py scripts/verify_cuda_generation.py scripts/verify_project.py tests/test_qasper_study.py tests/test_multimodal_selection.py

typecheck:
	uv run mypy

verify:
	uv run python scripts/verify_project.py

reproduce-qasper:
	uv run python scripts/reproduce.py --split test --allow-test

reproduce-dev:
	uv run python scripts/reproduce.py --split validation

reproduce: reproduce-v2

reproduce-v2:
	uv run python scripts/reproduce_multimodal.py

reproduce-v2-dev:
	uv run python scripts/download_multimodal_benchmarks.py
	uv run python scripts/multimodal_dataset_stats.py
	uv run python -m eval.multimodal_selection --dataset mmdocrag --split dev
	uv run python -m eval.multimodal_selection --dataset spiqa --split dev

run-v2-tests:
	uv run python scripts/download_multimodal_benchmarks.py
	uv run python -m eval.multimodal_selection --dataset mmdocrag --split test --allow-heldout
	uv run python -m eval.multimodal_selection --dataset spiqa --split test --allow-heldout

