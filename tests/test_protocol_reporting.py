from __future__ import annotations

import pytest

from woundscope.protocol import resolve_cross_split_policy
from woundscope.reporting import select_error_cases


def test_cross_split_policy_refuses_or_excludes() -> None:
    summary = {
        "exact_cross_split": [
            {
                "splits": ["train", "validation"],
                "samples": ["train/train-id", "validation/val-id"],
            }
        ]
    }
    with pytest.raises(RuntimeError, match="Exact image duplicates"):
        resolve_cross_split_policy(summary, "error")
    exclusions, record = resolve_cross_split_policy(summary, "exclude_train")
    assert exclusions == {"train/train-id"}
    assert record["policy"] == "exclude_train"


def test_error_gallery_selection_is_rule_based() -> None:
    records = [
        {
            "sample_id": "a",
            "dice": 0.9,
            "target_ratio": 0.2,
            "brightness": 90,
            "false_positive_ratio": 0.01,
        },
        {
            "sample_id": "b",
            "dice": 0.1,
            "target_ratio": 0.01,
            "brightness": 50,
            "false_positive_ratio": 0.02,
        },
        {
            "sample_id": "c",
            "dice": 0.5,
            "target_ratio": 0.1,
            "brightness": 70,
            "false_positive_ratio": 0.3,
        },
    ]
    selected = select_error_cases(records)
    assert selected["best"]["sample_id"] == "a"
    assert selected["worst"]["sample_id"] == "b"
    assert selected["small_area"]["sample_id"] == "b"
    assert selected["low_light"]["sample_id"] == "b"
    assert selected["background_interference"]["sample_id"] == "c"
