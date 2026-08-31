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
        build_site,
        normalize_site_source_sha,
        source_date_epoch_for_commit,
    )

    parser = argparse.ArgumentParser(description="Build the deterministic WoundScope Pages tree.")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site-source", required=True)
    arguments = parser.parse_args()

    repository = arguments.repository
    try:
        site_source_sha = normalize_site_source_sha(repository, arguments.site_source)
        result = build_site(
            repository=repository,
            output=arguments.output,
            site_source_sha=site_source_sha,
            source_date_epoch=source_date_epoch_for_commit(repository, site_source_sha),
        )
    except PagesAuditError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "manifest_sha256": result.manifest_sha256,
                "publish": str(result.publish),
                "publish_tree_sha256": result.publish_tree_sha256,
                "sbom_sha256": result.sbom_sha256,
                "site_source_sha": result.site_source_sha,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
