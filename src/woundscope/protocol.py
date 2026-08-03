"""Scientific guardrails derived from the validated FUSeg manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_data_summary(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cross_split_training_exclusions(summary: dict[str, Any]) -> set[str]:
    """Return official-train keys whose exact bytes occur in another official split."""

    exclusions: set[str] = set()
    for finding in summary.get("exact_cross_split", []):
        if "train" not in finding.get("splits", []):
            continue
        for sample in finding.get("samples", []):
            if "/" not in sample:
                raise RuntimeError(
                    "Data summary predates split-qualified duplicate keys; rerun download_data.py."
                )
            if sample.startswith("train/"):
                exclusions.add(sample)
    return exclusions


def resolve_cross_split_policy(
    summary: dict[str, Any], policy: str
) -> tuple[set[str], dict[str, Any]]:
    """Refuse contaminated training unless an explicit mitigation policy is selected."""

    findings = summary.get("exact_cross_split", [])
    if not findings:
        return set(), {"policy": "none_needed", "excluded_training_samples": []}
    if policy == "error":
        raise RuntimeError(
            "Exact image duplicates cross official splits. Select an explicit reviewed "
            "cross-split policy before training; recommended: exclude_train."
        )
    if policy != "exclude_train":
        raise ValueError(f"Unsupported cross-split policy: {policy}")
    exclusions = cross_split_training_exclusions(summary)
    return exclusions, {
        "policy": policy,
        "excluded_training_samples": sorted(exclusions),
        "finding_count": len(findings),
    }


def validate_exclude_train_contract(
    summary: dict[str, Any],
    manifest_rows: list[dict[str, str]],
    *,
    expected_exclusion_count: int,
    expected_validation_count: int,
    split_seed: int,
) -> dict[str, Any]:
    """Verify that the approved mitigation changes training only.

    Exact copies are removed from the official-train pool. Official validation remains intact,
    and duplicate groups in the retained official-train rows may not cross internal train/dev.
    """

    exclusions = cross_split_training_exclusions(summary)
    if len(exclusions) != expected_exclusion_count:
        raise RuntimeError(
            "Unexpected exact-copy exclusion count: "
            f"expected {expected_exclusion_count}, found {len(exclusions)}"
        )
    row_keys = {f"{row['split']}/{row['sample_id']}" for row in manifest_rows}
    missing = sorted(exclusions - row_keys)
    if missing:
        raise RuntimeError(f"Excluded training samples are absent from the manifest: {missing}")
    if any(not key.startswith("train/") for key in exclusions):
        raise RuntimeError("exclude_train attempted to exclude a non-training sample")

    validation_rows = [row for row in manifest_rows if row["split"] == "validation"]
    summary_validation = int(summary.get("counts", {}).get("validation", -1))
    if (
        summary_validation != expected_validation_count
        or len(validation_rows) != expected_validation_count
    ):
        raise RuntimeError(
            "Official validation was not retained intact: "
            f"summary={summary_validation}, manifest={len(validation_rows)}, "
            f"expected={expected_validation_count}"
        )
    if any(row["internal_split"] != "official_validation" for row in validation_rows):
        raise RuntimeError("Official validation contains rows assigned outside locked validation")

    group_splits: dict[str, set[str]] = {}
    for row in manifest_rows:
        key = f"{row['split']}/{row['sample_id']}"
        internal_split = row["internal_split"]
        if row["split"] != "train" or key in exclusions or internal_split not in {"train", "dev"}:
            continue
        group_splits.setdefault(row["duplicate_group"], set()).add(internal_split)
    leaking_groups = sorted(
        group for group, internal_splits in group_splits.items() if len(internal_splits) > 1
    )
    if leaking_groups:
        raise RuntimeError(
            "Retained duplicate groups cross internal train/dev: " + ", ".join(leaking_groups)
        )

    return {
        "policy": "exclude_train",
        "excluded_training_samples": sorted(exclusions),
        "finding_count": len(summary.get("exact_cross_split", [])),
        "retained_official_validation": len(validation_rows),
        "internal_split_seed": split_seed,
        "duplicate_group_isolation": True,
    }
