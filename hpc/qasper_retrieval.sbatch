#!/bin/bash
# Full frozen test retrieval run. Submit once, after validation choices are fixed.
# NOT VERIFIED on the university cluster; this workspace cannot access it.
# sbatch hpc/qasper_retrieval.sbatch
#SBATCH --job-name=docrag-qasper
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=results/slurm-qasper-%j.out

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
uv sync --locked
uv run python scripts/download_qasper.py
uv run python -m eval.qasper_study \
  --split test \
  --allow-test \
  --systems bm25,dense,hybrid,rerank,mmr,structure \
  --top-k 10 \
  --candidate-k 40
