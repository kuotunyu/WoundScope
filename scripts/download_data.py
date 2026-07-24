"""Download the pinned official FUSeg data and validate every sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from woundscope.config import load_config
from woundscope.data_download import ensure_sparse_checkout
from woundscope.data_integrity import DataIntegrityError, validate_fuseg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--allow-cross-split-exact", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)
    data_config = config["data"]
    data_root = (args.data_root or Path(data_config["root"])).resolve()
    checkout_root = data_root / data_config["raw_subdirectory"]
    if args.skip_download:
        challenge_dir = checkout_root / Path(data_config["source_subdirectory"])
    else:
        challenge_dir = ensure_sparse_checkout(
            data_config["source_repository"],
            data_config["source_revision"],
            data_config["source_subdirectory"],
            checkout_root,
        )
    manifest_path = data_root / data_config["manifest_subdirectory"] / "data_manifest.csv"
    try:
        summary = validate_fuseg(
            challenge_dir,
            manifest_path,
            near_duplicate_hamming=int(data_config["near_duplicate_hamming"]),
            dev_fraction=float(data_config["internal_dev_fraction"]),
            seed=int(data_config["split_seed"]),
            expected_counts={"train": 810, "validation": 200, "test": 200},
            allow_cross_split_exact=args.allow_cross_split_exact,
        )
    except DataIntegrityError as exc:
        print(json.dumps({"status": "failed", "issues": exc.issues}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps({"status": "ok", **summary}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
