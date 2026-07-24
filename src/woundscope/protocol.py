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
