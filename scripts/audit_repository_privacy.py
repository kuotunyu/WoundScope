from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(REPOSITORY_SOURCE))


def main() -> int:
    from woundscope.repository_privacy import audit_repository_privacy

    parser = argparse.ArgumentParser(
        description="Audit tracked WoundScope files for prohibited private artifacts."
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    report = audit_repository_privacy(arguments.repository)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
