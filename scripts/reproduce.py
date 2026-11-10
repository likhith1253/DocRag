"""Run the frozen CPU retrieval study and generate analysis artifacts."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("validation", "test"), default="test")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args()
    if args.split == "test" and not args.allow_test:
        parser.error("The test split requires --allow-test after validation choices are frozen.")
    subprocess.run([sys.executable, "scripts/download_qasper.py"], cwd=ROOT, check=True)
    systems = "bm25,dense,hybrid,rerank,mmr,structure"
    command = [
        sys.executable, "-m", "eval.qasper_study", "--split", args.split,
        "--systems", systems, "--top-k", "10", "--candidate-k", "40",
    ]
    if args.split == "test":
        command.append("--allow-test")
    result = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    raw_dir = ROOT / result.stdout.strip().splitlines()[-1]
    raw_path = raw_dir / "raw.json"
    subprocess.run([sys.executable, "-m", "eval.failure_analysis", str(raw_path)], cwd=ROOT, check=True)
    table_paths = subprocess.run(
        [sys.executable, "-m", "eval.paper_table", str(raw_path)],
        cwd=ROOT, check=True, text=True, capture_output=True,
    ).stdout.strip().splitlines()
    generated = ROOT / "paper" / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    shutil.copy2(table_paths[1], generated / "main_results.tex")
    shutil.copy2(table_paths[2], generated / "pairwise_comparisons.tex")
    shutil.copy2(raw_dir / "summary.csv", generated / "main_results.csv")
    shutil.copy2(raw_dir / "summary_metadata.json", generated / "main_results_metadata.json")
    shutil.copy2(raw_dir / "failure_analysis.tex", generated / "failure_analysis.tex")
    shutil.copy2(raw_dir / "failure_examples.tex", generated / "failure_examples.tex")
    print(raw_path)


if __name__ == "__main__":
    main()
