"""
API security helpers: API-key authentication and filesystem confinement.

Authentication
--------------
* If ``DOCRAG_API_KEY`` is set, every protected endpoint requires a matching
  ``X-API-Key`` header (compared in constant time).
* If it is NOT set, protected endpoints only answer clients connecting from the
  loopback interface. Remote access therefore fails closed instead of silently
  being open. NOTE: behind a reverse proxy running on the same host every
  request looks like loopback, so set ``DOCRAG_API_KEY`` in that case.

Filesystem confinement
----------------------
``source_path`` values supplied through the API are server-side paths that get
read and indexed. They are resolved (symlinks and ``..`` collapsed) and must be
inside one of the directories listed in ``DOCRAG_DATA_ROOTS`` (``os.pathsep``
separated; default: ``./demo_dataset``, ``./papers`` and ``./uploads``).
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import List, Optional

from fastapi import Header, HTTPException, Request

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _configured_key() -> str:
    return os.environ.get("DOCRAG_API_KEY", "").strip()


def is_authorized(request: Request, x_api_key: Optional[str]) -> bool:
    key = _configured_key()
    if key:
        return bool(x_api_key) and hmac.compare_digest(
            x_api_key.encode("utf-8"), key.encode("utf-8")
        )
    host = request.client.host if request.client else ""
    return host in _LOOPBACK_HOSTS


def require_api_key(
    request: Request, x_api_key: Optional[str] = Header(default=None)
) -> None:
    """FastAPI dependency guarding every non-public endpoint."""
    if is_authorized(request, x_api_key):
        return
    if _configured_key():
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    raise HTTPException(
        status_code=403,
        detail="Remote access is disabled. Set DOCRAG_API_KEY to enable it.",
    )


def allowed_data_roots() -> List[Path]:
    raw = os.environ.get("DOCRAG_DATA_ROOTS", "").strip()
    if raw:
        roots = [p for p in raw.split(os.pathsep) if p.strip()]
    else:
        roots = ["demo_dataset", "papers", "uploads"]
    return [Path(r).expanduser().resolve() for r in roots]


def validate_source_path(source_path: str) -> str:
    """
    Validate a (possibly ``;``-separated) list of server-side source paths.

    Returns the normalised, resolved paths joined with ``;``.
    Raises HTTP 400 for malformed/non-existent paths and 403 for paths that
    escape the allowed data roots.
    """
    if not source_path or "\x00" in source_path:
        raise HTTPException(status_code=400, detail="Invalid source_path.")
    roots = allowed_data_roots()
    resolved: List[str] = []
    for raw in [p.strip() for p in source_path.split(";") if p.strip()]:
        try:
            candidate = Path(raw).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid source_path.")
        if not any(candidate == r or candidate.is_relative_to(r) for r in roots):
            raise HTTPException(
                status_code=403,
                detail="source_path is outside the allowed data directories "
                "(see DOCRAG_DATA_ROOTS).",
            )
        if not candidate.exists():
            raise HTTPException(status_code=400, detail="source_path does not exist.")
        resolved.append(str(candidate))
    if not resolved:
        raise HTTPException(status_code=400, detail="Invalid source_path.")
    return ";".join(resolved)
