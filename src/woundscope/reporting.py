"""Deterministic, non-cherry-picked error-analysis case selection."""

from __future__ import annotations

from typing import Any


def select_error_cases(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Select one record for each locked gallery category from measured properties."""

    if not records:
        raise ValueError("Error analysis requires at least one record")
    required = {"dice", "target_ratio", "brightness", "false_positive_ratio"}
    for record in records:
        missing = required - record.keys()
        if missing:
            raise ValueError(f"Error-analysis record is missing fields: {sorted(missing)}")
    return {
        "best": max(records, key=lambda row: (row["dice"], str(row.get("sample_id", "")))),
        "worst": min(records, key=lambda row: (row["dice"], str(row.get("sample_id", "")))),
        "small_area": min(
            (row for row in records if row["target_ratio"] > 0),
            key=lambda row: (row["target_ratio"], str(row.get("sample_id", ""))),
            default=min(records, key=lambda row: row["target_ratio"]),
        ),
        "low_light": min(
            records, key=lambda row: (row["brightness"], str(row.get("sample_id", "")))
        ),
        "background_interference": max(
            records,
            key=lambda row: (row["false_positive_ratio"], str(row.get("sample_id", ""))),
        ),
    }
