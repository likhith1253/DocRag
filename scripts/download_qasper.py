"""Download and verify the frozen, CC BY 4.0 QASPER parquet release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/frozen/qasper_manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = ROOT / "data/downloads/qasper"
    base.mkdir(parents=True, exist_ok=True)
    for split, metadata in manifest["files"].items():
        path = base / f"{split}.parquet"
        if not path.exists():
            url = (
                "https://huggingface.co/datasets/allenai/qasper/resolve/"
                f"{manifest['revision']}/qasper/qasper-{split}.parquet"
            )
            with requests.get(url, stream=True, timeout=(20, 180)) as response:
                response.raise_for_status()
                with path.open("wb") as output:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            output.write(chunk)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != metadata["sha256"]:
            path.unlink(missing_ok=True)
            raise ValueError(f"SHA-256 mismatch for {split}: {digest}")
        print(f"{split}: verified {metadata['bytes']} bytes ({digest})")


if __name__ == "__main__":
    main()
