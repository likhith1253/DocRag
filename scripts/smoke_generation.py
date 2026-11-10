"""Exercise the default CPU generator without using evaluation data."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from settings import get_settings
from llm.backend import generate

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = get_settings()
    if settings.device.lower() != "cpu":
        raise RuntimeError("This smoke script is for the CPU path; leave DOCRAG__DEVICE=cpu.")
    prompt = "Reply with the single word READY."
    config = {
        "model": settings.doc_agent_model,
        "model_revision": settings.hf_model_revision if settings.doc_agent_model == settings.hf_model else None,
        "backend": settings.llm_backend,
        "device": settings.device,
        "temperature": settings.generation.temperature,
        "seed": settings.generation.seed,
        "num_predict": min(settings.generation.num_predict, 16),
        "prompt": prompt,
    }
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    started = time.perf_counter()
    os.environ["DOCRAG_FORCE_GENERATION"] = "1"
    try:
        response = generate(prompt, "doc_agent_model", request_id="cpu-generator-smoke")
        elapsed = time.perf_counter() - started
        record = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "git_worktree_dirty": dirty,
            "config": config,
            "config_sha256": config_hash,
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("torch", "transformers", "sentence-transformers")
            },
            "elapsed_seconds": elapsed,
            "status": "completed",
            "response": response,
        }
    except Exception as exc:
        record = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "git_worktree_dirty": dirty,
            "config": config,
            "config_sha256": config_hash,
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("torch", "transformers", "sentence-transformers")
            },
            "elapsed_seconds": time.perf_counter() - started,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + config_hash[:12] + "_" + commit[:10]
    output = ROOT / "results" / "generation_smoke" / run_name / "raw.json"
    output.parent.mkdir(parents=True, exist_ok=False)
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output.relative_to(ROOT))
    if record["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
