from __future__ import annotations

import pytest

import woundscope.protocol as protocol
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


def test_exclude_train_contract_retains_validation_and_group_isolation() -> None:
    summary = {
        "counts": {"train": 2, "validation": 1, "test": 1},
        "exact_cross_split": [
            {
                "splits": ["train", "validation"],
                "samples": ["train/train-copy", "validation/locked-sample"],
            }
        ],
    }
    rows = [
        {
            "split": "train",
            "sample_id": "train-copy",
            "internal_split": "train",
            "duplicate_group": "dup-exact",
        },
        {
            "split": "train",
            "sample_id": "clean-train",
            "internal_split": "dev",
            "duplicate_group": "dup-clean",
        },
        {
            "split": "validation",
            "sample_id": "locked-sample",
            "internal_split": "official_validation",
            "duplicate_group": "dup-exact",
        },
        {
            "split": "test",
            "sample_id": "blind-sample",
            "internal_split": "official_test",
            "duplicate_group": "dup-test",
        },
    ]

    record = protocol.validate_exclude_train_contract(
        summary,
        rows,
        expected_exclusion_count=1,
        expected_validation_count=1,
        split_seed=42,
    )

    assert record["policy"] == "exclude_train"
    assert record["excluded_training_samples"] == ["train/train-copy"]
    assert record["retained_official_validation"] == 1
    assert record["internal_split_seed"] == 42
    assert record["duplicate_group_isolation"] is True


def test_exclude_train_contract_rejects_internal_group_leakage() -> None:
    summary = {"counts": {"validation": 1}, "exact_cross_split": []}
    rows = [
        {
            "split": "train",
            "sample_id": "a",
            "internal_split": "train",
            "duplicate_group": "dup-leak",
        },
        {
            "split": "train",
            "sample_id": "b",
            "internal_split": "dev",
            "duplicate_group": "dup-leak",
        },
        {
            "split": "validation",
            "sample_id": "v",
            "internal_split": "official_validation",
            "duplicate_group": "dup-v",
        },
    ]

    with pytest.raises(RuntimeError, match="duplicate groups cross internal train/dev"):
        protocol.validate_exclude_train_contract(
            summary,
            rows,
            expected_exclusion_count=0,
            expected_validation_count=1,
            split_seed=42,
        )


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
