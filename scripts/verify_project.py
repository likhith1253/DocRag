"""Run and archive the project's final local lint, type, test, and build checks."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LINT_TARGETS = [
    "settings.py", "llm/cache.py", "retrieval/query_analyzer.py", "retrieval/paper_matcher.py",
    "eval/qasper_study.py", "eval/failure_analysis.py", "eval/paper_table.py",
    "scripts/dataset_stats.py", "scripts/download_qasper.py", "scripts/reproduce.py",
    "scripts/smoke_generation.py", "scripts/verify_cuda_generation.py", "scripts/verify_project.py",
    "tests/test_qasper_study.py",
]
COMMANDS = [
    [sys.executable, "-m", "ruff", "check", *LINT_TARGETS],
    [sys.executable, "-m", "mypy"],
    [sys.executable, "-m", "pytest", "-q", "-m", "not slow and not gpu"],
    ["uv", "build"],
]


def main() -> None:
    config = {"commands": COMMANDS, "python": sys.version, "platform": platform.platform()}
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    results: list[dict[str, Any]] = []
    for command in COMMANDS:
        try:
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
            results.append({
                "command": command, "returncode": completed.returncode,
                "stdout": completed.stdout, "stderr": completed.stderr,
            })
        except OSError as exc:
            results.append({"command": command, "returncode": 127, "stdout": "", "stderr": str(exc)})
        if results[-1]["returncode"] != 0:
            break
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_worktree_dirty_at_start": dirty,
        "config_sha256": config_hash,
        "hardware": {"platform": platform.platform(), "cpu": platform.processor()},
        "checks": results,
        "status": "passed" if len(results) == len(COMMANDS) and all(x["returncode"] == 0 for x in results) else "failed",
    }
    folder = ROOT / "results" / "verification"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{config_hash[:10]}.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output.relative_to(ROOT))
    if payload["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
