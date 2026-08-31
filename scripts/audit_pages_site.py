from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))


def main() -> int:
    from scripts.pages_site.integrity import (
        PagesAuditError,
        compare_publish_trees,
        record_central_seal,
        seal_review,
        verify_publish_tree,
    )

    parser = argparse.ArgumentParser(description="Audit the deterministic WoundScope Pages tree.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--publish", type=Path, required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--left", type=Path, required=True)
    compare_parser.add_argument("--right", type=Path, required=True)

    seal_parser = subparsers.add_parser("seal-review")
    seal_parser.add_argument("--publish", type=Path, required=True)
    seal_parser.add_argument("--reports", type=Path, required=True)
    seal_parser.add_argument("--output", type=Path, required=True)

    central_parser = subparsers.add_parser("record-central-seal")
    central_parser.add_argument("--receipt", type=Path, required=True)
    central_parser.add_argument("--output", type=Path, required=True)
    central_parser.add_argument("--approved-site-source", required=True)
    central_parser.add_argument("--reviewer", required=True)
    central_parser.add_argument("--approval-id", required=True)

    arguments = parser.parse_args()
    try:
        if arguments.command == "verify":
            verified = verify_publish_tree(arguments.publish)
            payload = {
                "manifest_sha256": verified.manifest_sha256,
                "publish": str(verified.publish),
                "publish_tree_sha256": verified.publish_tree_sha256,
                "sbom_sha256": verified.sbom_sha256,
                "site_source_sha": verified.site_source_sha,
            }
        elif arguments.command == "compare":
            compare_publish_trees(arguments.left, arguments.right)
            payload = {"status": "ok"}
        elif arguments.command == "seal-review":
            payload = {
                "receipt": str(seal_review(arguments.publish, arguments.reports, arguments.output))
            }
        else:
            payload = {
                "seal": str(
                    record_central_seal(
                        receipt=arguments.receipt,
                        output=arguments.output,
                        approved_site_source=arguments.approved_site_source,
                        reviewer=arguments.reviewer,
                        approval_id=arguments.approval_id,
                    )
                )
            }
    except PagesAuditError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
