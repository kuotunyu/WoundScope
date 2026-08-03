"""Build and verify a code-only Hugging Face Space candidate and ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from woundscope.bundles import build_huggingface_space_bundle


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _summary(output_directory: Path, output_zip: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "verified",
        "output_directory": str(output_directory.resolve()),
        "output_zip": str(output_zip.resolve()),
        "source_commit": manifest["source_commit"],
        "file_count": len(manifest["files"]),
        "zip_sha256": _sha256_file(output_zip.resolve()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/huggingface-space/candidate"),
    )
    parser.add_argument(
        "--output-zip",
        type=Path,
        default=Path("artifacts/huggingface-space/WoundScope_hf_space_code_only.zip"),
    )
    args = parser.parse_args()
    manifest = build_huggingface_space_bundle(args.repository, args.output_dir, args.output_zip)
    print(
        json.dumps(
            _summary(args.output_dir, args.output_zip, manifest), ensure_ascii=False, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
