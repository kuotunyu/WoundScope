"""Build and optionally clean-extract/verify an immutable safe Colab source ZIP."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from woundscope.bundles import build_source_bundle, extract_bundle


def _verify_clean_extract(bundle: Path, source_commit: str) -> None:
    with tempfile.TemporaryDirectory(prefix="woundscope-source-verify-") as temporary:
        root = Path(temporary)
        extract_bundle(
            bundle,
            root,
            expected_kind="source",
            expected_source_commit=source_commit,
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = (
            str(root / "src") + os.pathsep + environment.get("PYTHONPATH", "")
        )
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json; import woundscope; from pathlib import Path; "
                    "notebook=json.loads(Path('notebooks/01_train_colab.ipynb').read_text(encoding='utf-8')); "
                    "assert notebook['nbformat'] == 4"
                ),
            ],
            cwd=root,
            env=environment,
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=root,
            env=environment,
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/handoff/WoundScope_colab_source.zip"),
    )
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    manifest = build_source_bundle(args.repository, args.output)
    if args.verify:
        _verify_clean_extract(args.output.resolve(), str(manifest["source_commit"]))
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "source_commit": manifest["source_commit"],
                "file_count": len(manifest["files"]),
                "verified": args.verify,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
