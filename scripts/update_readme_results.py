"""Update README markers only from a verified full multi-seed results artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from woundscope.readme_results import render_results_table, replace_marker_region


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--readme", type=Path, default=Path("README.md"))
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    payload = json.loads(args.results.read_text(encoding="utf-8"))
    rendered = render_results_table(payload)
    updated = replace_marker_region(args.readme.read_text(encoding="utf-8"), rendered)
    temporary = args.readme.with_suffix(args.readme.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    temporary.replace(args.readme)
    print(args.readme)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
