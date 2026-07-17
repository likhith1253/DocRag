"""
eval.benchmark.artifacts.manifest
===================================
Experiment manifest generation (Amendment 3).

Every experiment run generates a manifest.json containing:
  - git commit hash
  - config hash (SHA-256 of config.yaml)
  - dataset hash (SHA-256 of dataset content — from BenchmarkDataset.compute_hash())
  - environment hash (SHA-256 of key package versions)
  - model versions (embedding model, reranker, LLM models from config)
  - timestamp (UTC ISO 8601)
  - experiment config hash
  - all random seeds used

This enables exact reproducibility auditing: two runs with identical manifests
must produce bit-identical results (modulo LLM stochasticity).

Research mapping:
  All RQs — reproducibility requirement for every reported experiment.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def _get_git_commit_hash() -> str:
    """
    Get the current git commit hash of the repository.

    Returns "unknown" if git is not available or the directory is not a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            ))),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return "unknown"


def _get_git_dirty_status() -> bool:
    """
    Check if the working tree has uncommitted changes.

    Returns True if dirty (uncommitted changes), False if clean.
    Returns None if git is not available.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            ))),
        )
        if result.returncode == 0:
            return len(result.stdout.strip()) > 0
        return None
    except Exception:
        return None


def _hash_file(path: str) -> str:
    """Compute SHA-256 hash of a file's contents. Returns 'missing' if file not found."""
    if not os.path.exists(path):
        return "missing"
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _hash_config(config_path: str) -> str:
    """Hash config.yaml for manifest."""
    return _hash_file(config_path)


def _get_key_package_versions() -> Dict[str, str]:
    """
    Get versions of key packages relevant to reproducibility.
    Returns {"package": "version"} for each installed package.
    """
    packages = [
        "sentence_transformers",
        "qdrant_client",
        "numpy",
        "scipy",
        "torch",
        "transformers",
        "rank_bm25",
        "rouge_score",
        "nltk",
        "matplotlib",
        "langgraph",
        "networkx",
        "pyyaml",
    ]
    versions = {}
    for pkg in packages:
        try:
            import importlib.metadata
            versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            versions[pkg] = "not_installed"
    return versions


def _hash_environment(versions: Dict[str, str]) -> str:
    """Compute SHA-256 hash of the package version dict."""
    content = json.dumps(versions, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_model_versions(config_path: str) -> Dict[str, str]:
    """
    Extract model names from config.yaml for the manifest.

    These are versioned implicitly by their names (HuggingFace model IDs).
    The manifest records exactly which models were used.
    """
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return {
            "embedding_model": config.get("embedding_model", "unknown"),
            "reranker_model": config.get("reranker_model", "unknown"),
            "code_agent_model": config.get("code_agent_model", "unknown"),
            "reasoning_agent_model": config.get("reasoning_agent_model", "unknown"),
            "llm_backend": config.get("llm_backend", "unknown"),
        }
    except Exception:
        return {}


def _hash_dict(d: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of a JSON-serializable dict."""
    content = json.dumps(d, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_manifest(
    experiment_config: Dict[str, Any],
    dataset_hash: str,
    seeds: Dict[str, Any],
    output_dir: str,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate and save the experiment manifest.

    The manifest uniquely identifies an experiment run and enables exact
    reproducibility auditing.

    Parameters
    ----------
    experiment_config : dict
        The full experiment YAML config (already loaded as dict).
    dataset_hash : str
        SHA-256 hash of the dataset (from BenchmarkDataset.compute_hash()).
    seeds : dict
        All random seeds used in the experiment (system-level, per-run).
    output_dir : str
        Directory where manifest.json will be written.
    config_path : str, optional
        Path to config.yaml. Defaults to repo root config.yaml.

    Returns
    -------
    dict — the manifest contents.
    """
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            ))),
            "config.yaml"
        )

    git_commit = _get_git_commit_hash()
    git_dirty = _get_git_dirty_status()
    config_hash = _hash_config(config_path)
    experiment_config_hash = _hash_dict(experiment_config)
    package_versions = _get_key_package_versions()
    environment_hash = _hash_environment(package_versions)
    model_versions = _get_model_versions(config_path)

    manifest = {
        "manifest_version": "1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": experiment_config.get("experiment_id", "unknown"),
        "reproducibility": {
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "config_hash": config_hash,
            "experiment_config_hash": experiment_config_hash,
            "dataset_hash": dataset_hash,
            "environment_hash": environment_hash,
        },
        "model_versions": model_versions,
        "package_versions": package_versions,
        "seeds": seeds,
        "python_version": sys.version,
        "platform": platform.platform(),
        "experiment_config": experiment_config,
    }

    # Warn if git tree is dirty (results may not be reproducible)
    if git_dirty:
        manifest["warnings"] = [
            "Working tree has uncommitted changes. "
            "Results may not be reproducible from git commit alone. "
            "Commit all changes before running final reported experiments."
        ]

    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest
