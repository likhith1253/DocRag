"""
eval.benchmark.artifacts.environment
======================================
System environment snapshot for reproducibility.

Captures: Python version, OS, CPU, RAM, installed packages, git status.
Written to environment/ directory under the experiment output.

Research mapping:
  All RQs — environment snapshot is required for every published experiment.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, Any


def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information."""
    info: Dict[str, Any] = {
        "processor": platform.processor(),
        "machine": platform.machine(),
    }
    try:
        import psutil
        info["physical_cores"] = psutil.cpu_count(logical=False)
        info["logical_cores"] = psutil.cpu_count(logical=True)
        info["cpu_freq_mhz"] = psutil.cpu_freq().max if psutil.cpu_freq() else "unknown"
    except ImportError:
        info["note"] = "psutil not installed — detailed CPU info unavailable"
    return info


def get_ram_info() -> Dict[str, Any]:
    """Get RAM information."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "available_gb": round(mem.available / (1024 ** 3), 2),
        }
    except ImportError:
        return {"note": "psutil not installed"}


def get_gpu_info() -> Dict[str, Any]:
    """Get GPU information if available."""
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "available": True,
                "device_count": torch.cuda.device_count(),
                "device_name": torch.cuda.get_device_name(0),
                "memory_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 2),
            }
        return {"available": False}
    except ImportError:
        return {"available": False, "note": "torch not installed"}


def get_installed_packages() -> Dict[str, str]:
    """Get all installed packages and their versions."""
    try:
        import importlib.metadata
        packages = {}
        for dist in importlib.metadata.distributions():
            packages[dist.metadata["Name"]] = dist.version
        return packages
    except Exception:
        return {}


def capture_environment(output_dir: str) -> Dict[str, Any]:
    """
    Capture complete environment snapshot and write to output_dir/environment/.

    Parameters
    ----------
    output_dir : str
        Experiment output directory root.

    Returns
    -------
    dict — the environment snapshot.
    """
    env_dir = os.path.join(output_dir, "environment")
    os.makedirs(env_dir, exist_ok=True)

    # System info
    system_info = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "os": platform.system(),
        "os_version": platform.version(),
        "hostname": platform.node(),
        "cpu": get_cpu_info(),
        "ram": get_ram_info(),
        "gpu": get_gpu_info(),
    }

    with open(os.path.join(env_dir, "system_info.json"), "w", encoding="utf-8") as f:
        json.dump(system_info, f, indent=2)

    # All installed packages (pip freeze equivalent)
    packages = get_installed_packages()
    with open(os.path.join(env_dir, "packages.json"), "w", encoding="utf-8") as f:
        json.dump(packages, f, indent=2, sort_keys=True)

    # Combined snapshot
    snapshot = {
        "system_info": system_info,
        "packages": packages,
    }

    return snapshot


def capture_seeds(
    experiment_seed: int,
    run_seeds: Dict[int, int],
    output_dir: str,
) -> None:
    """
    Save all random seeds used in the experiment to environment/seeds.json.

    Parameters
    ----------
    experiment_seed : int
        Base seed from the experiment config.
    run_seeds : dict[int, int]
        Mapping from run_index → actual seed used.
    output_dir : str
        Experiment output directory root.
    """
    env_dir = os.path.join(output_dir, "environment")
    os.makedirs(env_dir, exist_ok=True)
    seeds_data = {
        "experiment_seed": experiment_seed,
        "run_seeds": run_seeds,
        "note": "Each run uses seed = experiment_seed + run_index for reproducibility.",
    }
    with open(os.path.join(env_dir, "seeds.json"), "w", encoding="utf-8") as f:
        json.dump(seeds_data, f, indent=2)
