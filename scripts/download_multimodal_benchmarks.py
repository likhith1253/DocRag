"""Download the exact public benchmark files frozen in the study manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/frozen/multimodal_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for dataset in manifest["datasets"].values():
        for split in ("development", "test"):
            record = dataset[split]
            target = ROOT / record["file"]
            if target.exists() and target.stat().st_size == record["bytes"] and sha256(target) == record["sha256"]:
                print(f"verified {target.relative_to(ROOT)}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            dataset_id = dataset["repository"]
            revision = dataset["revision"]
            hf_path = record["hf_path"]
            url = f"https://huggingface.co/datasets/{dataset_id}/resolve/{revision}/{hf_path}"
            temporary = target.with_suffix(target.suffix + ".partial")
            with requests.get(url, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
            if temporary.stat().st_size != record["bytes"] or sha256(temporary) != record["sha256"]:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"Downloaded file failed frozen hash check: {target}")
            temporary.replace(target)
            print(f"downloaded and verified {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
