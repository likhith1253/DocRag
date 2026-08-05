#!/bin/bash
# run_on_hpc.sh - Wrapper to ensure dependencies are installed before running

echo "Checking and installing required dependencies..."
pip3 install --user -r requirements.txt

echo "Dependencies installed. Running verification suite..."
export DISABLE_PROMPT_CACHE=1
export ENABLE_PROMPT_CACHE=0
python3 scripts/run_hpc_verification.py
