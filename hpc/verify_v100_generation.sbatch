#!/bin/bash
# NOT VERIFIED: one-shot diagnostic for the reported V100 memory/driver issue.
# Submit from the repository root on the university cluster.
# sbatch hpc/verify_v100_generation.sbatch
# It runs eager and SDPA variants separately, never concurrently on one GPU.
#SBATCH --job-name=docrag-v100-diagnostic
#SBATCH --partition=gpu
#SBATCH --gres=gpu:v100:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:45:00
#SBATCH --array=0-1
#SBATCH --output=results/slurm-v100-%A_%a.out

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
uv sync --locked
if [[ "${SLURM_ARRAY_TASK_ID}" == "0" ]]; then
  ATTENTION="eager"
else
  ATTENTION="sdpa"
fi
uv run python scripts/verify_cuda_generation.py \
  --model Qwen/Qwen2.5-3B-Instruct \
  --prompt-tokens 7400 \
  --max-new-tokens 32 \
  --attention "${ATTENTION}"
