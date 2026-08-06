#!/bin/bash
# run_on_hpc.sh - Clean Virtual Environment Runner for HPC

echo "======================================================="
echo "Setting up Python Virtual Environment (venv)..."
echo "======================================================="

# Create a clean venv if it doesn't exist
if [ ! -d "hpc_venv" ]; then
    python3 -m venv hpc_venv
fi

# Activate virtual environment
source hpc_venv/bin/activate

echo "Installing/verifying requirements inside virtual environment..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo "======================================================="
echo "Dependencies ready. Executing production API benchmark..."
echo "======================================================="

export DISABLE_PROMPT_CACHE=1
export ENABLE_PROMPT_CACHE=0

python scripts/run_production_benchmark.py
