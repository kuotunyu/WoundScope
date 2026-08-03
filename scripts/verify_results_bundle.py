"""Verify and extract a WoundScope safe results ZIP for local release processing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from woundscope.bundles import extract_bundle
from woundscope.readme_results import validate_verified_results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--output", type=Path, default=Path("artifacts/verified"))
    args = parser.parse_args()

    manifest = extract_bundle(
        args.bundle,
        args.output,
        expected_kind="results",
        expected_source_commit=args.expected_source_commit,
    )
    verified_results = args.output / "aggregate" / "verified_results.json"
    if not verified_results.is_file():
        raise SystemExit("Safe result bundle is missing aggregate/verified_results.json")
    payload = json.loads(verified_results.read_text(encoding="utf-8"))
    validate_verified_results(payload)
    print(
        json.dumps(
            {
                "status": "verified",
                "source_commit": manifest["source_commit"],
                "file_count": len(manifest["files"]),
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
