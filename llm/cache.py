from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from settings import get_settings, resolve_project_path


def cache_key(model_id: str, prompt: str, decoding: Mapping[str, Any]) -> str:
    payload = {"model_id": model_id, "prompt": prompt, "decoding": dict(decoding)}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_path(key: str) -> Path:
    directory = resolve_project_path(get_settings().cache_dir) / "llm"
    return directory / key[:2] / f"{key}.json"


def read_cached(key: str) -> str | None:
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = payload.get("result")
        return result if isinstance(result, str) else None
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read LLM cache entry {path}: {exc}") from exc


def write_cached(key: str, result: str) -> Path:
    path = cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{key}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"key": key, "result": result}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise RuntimeError(f"Unable to write LLM cache entry {path}: {exc}") from exc
    return path
