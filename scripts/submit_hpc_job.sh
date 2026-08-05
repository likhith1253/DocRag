#!/bin/bash
#SBATCH --job-name=docrag_50runs
#SBATCH --output=logs/hpc_job_%j.out
#SBATCH --error=logs/hpc_job_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
#SBATCH --partition=gpu

echo "================================================================="
echo "DocumentRAG HPC 50-Query Comprehensive Verification Run"
echo "Host: $(hostname)"
echo "CUDA_VISIBLE_DEVICES: $CUDA_VISIBLE_DEVICES"
echo "Date: $(date)"
echo "================================================================="

# Force prompt cache disabled so every call hits live GPU inference
export DISABLE_PROMPT_CACHE=1
export ENABLE_PROMPT_CACHE=0

# Activate virtual environment if applicable
# source venv/bin/activate

python scripts/run_hpc_verification.py

echo "================================================================="
echo "Run Finished. Report saved to logs/hpc_50_runs_comprehensive_report.md"
echo "================================================================="
