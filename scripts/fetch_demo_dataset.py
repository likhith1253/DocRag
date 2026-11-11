#!/usr/bin/env python3
"""
Download the third-party demo papers listed in demo_dataset/MANIFEST.json.

The PDFs are not stored in git (they are other people's papers, ~90 MB). Each
entry with ``source == "arxiv"`` is fetched from arxiv.org by id and version
and written to the path recorded in the manifest. Entries with
``source == "bundled"`` are not on arXiv and are kept in the repository.

Usage:
    python scripts/fetch_demo_dataset.py            # fetch what is missing
    python scripts/fetch_demo_dataset.py --check    # only report what is missing

Notes:
  * Standard library only; no API keys needed.
  * Existing files are never overwritten.
  * arXiv occasionally re-renders a given version, so a SHA-256 mismatch is
    reported as a warning, not an error.
  * Be polite to arXiv: requests are spaced DELAY_S seconds apart.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "demo_dataset" / "MANIFEST.json"
DELAY_S = 3.0
USER_AGENT = "DocRag-demo-fetch/1.0 (research demo; https://github.com/likhith1253/DocRag)"


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--check", action="store_true", help="only list missing files")
    args = ap.parse_args()

    papers = json.loads(MANIFEST.read_text(encoding="utf-8"))["papers"]
    missing = [p for p in papers if not (ROOT / p["path"]).exists()]
    print(f"{len(papers) - len(missing)}/{len(papers)} files present, {len(missing)} missing")
    if args.check or not missing:
        for p in missing:
            print("  missing:", p["path"])
        return 1 if (args.check and missing) else 0

    failures = 0
    for i, p in enumerate(missing):
        dest = ROOT / p["path"]
        if p["source"] != "arxiv":
            print(f"  [SKIP] {p['path']}: bundled file is missing from this checkout")
            failures += 1
            continue
        url = f"https://arxiv.org/pdf/{p['arxiv_id']}v{p['version']}"
        try:
            data = _download(url)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  [FAIL] {url}: {exc}")
            failures += 1
            continue
        if not data.startswith(b"%PDF"):
            print(f"  [FAIL] {url}: response is not a PDF")
            failures += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        status = "ok" if hashlib.sha256(data).hexdigest() == p["sha256"] else "ok (hash differs from manifest)"
        print(f"  [{status}] {p['path']}")
        if i < len(missing) - 1:
            time.sleep(DELAY_S)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
