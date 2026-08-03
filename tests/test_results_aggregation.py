from __future__ import annotations

import importlib
import json

import pytest


def _module():
    return importlib.import_module("woundscope.results")


def _report(seed: int, confusions: list[dict[str, int]]) -> dict:
    return {
        "status": "completed",
        "split": "official_validation",
        "model": "unet_efficientnet_b0",
        "loss": "bce_dice",
        "seed": seed,
        "source_commit": "a" * 40,
        "config_sha256": f"{seed % 10}" * 64,
        "manifest_sha256": "b" * 64,
        "checkpoint_sha256": f"{(seed + 1) % 10}" * 64,
        "sample_order_sha256": "c" * 64,
        "calibration": {
            "temperature": 1.0,
            "threshold": 0.5,
            "confidence_cutoff": 0.2,
            "source_split": "dev",
        },
        "confidence": {
            "count": 2,
            "low_confidence_count": 0,
            "low_confidence_fraction": 0.0,
        },
        "confusions": confusions,
    }


def test_aggregate_recomputes_three_seed_metrics_and_removes_image_level_data() -> None:
    results = _module()
    perfect = {
        "true_positive": 10,
        "false_positive": 0,
        "false_negative": 0,
        "true_negative": 90,
    }
    missed = {
        "true_positive": 0,
        "false_positive": 0,
        "false_negative": 10,
        "true_negative": 90,
    }
    reports = [
        _report(42, [perfect, missed]),
        _report(43, [perfect, perfect]),
        _report(44, [missed, missed]),
    ]

    aggregate = results.aggregate_official_validation(reports, bootstrap_samples=50)

    assert aggregate["seeds"] == [42, 43, 44]
    assert aggregate["dice"]["mean"] == pytest.approx(0.5)
    assert aggregate["dice"]["std"] == pytest.approx(0.5)
    assert aggregate["dice"]["ddof"] == 1
    assert aggregate["bootstrap"]["samples"] == 50
    assert aggregate["bootstrap"]["cluster"] == "image"
    assert len(aggregate["bootstrap_distribution"]["dice"]) == 50
    assert aggregate["bootstrap_95_ci"]["dice"][0] <= 0.5
    assert aggregate["bootstrap_95_ci"]["dice"][1] >= 0.5
    serialized = json.dumps(aggregate)
    assert "sample_id" not in serialized
    assert "confusions" not in serialized


def test_aggregate_rejects_mixed_source_commits() -> None:
    results = _module()
    confusion = [
        {
            "true_positive": 1,
            "false_positive": 0,
            "false_negative": 0,
            "true_negative": 1,
        }
    ]
    reports = [_report(seed, confusion) for seed in (42, 43, 44)]
    reports[2]["source_commit"] = "d" * 40

    with pytest.raises(ValueError, match="source_commit"):
        results.aggregate_official_validation(reports, bootstrap_samples=10)


def test_aggregate_rejects_non_dev_calibration() -> None:
    results = _module()
    confusion = [
        {
            "true_positive": 1,
            "false_positive": 0,
            "false_negative": 0,
            "true_negative": 1,
        }
    ]
    reports = [_report(seed, confusion) for seed in (42, 43, 44)]
    reports[1]["calibration"]["source_split"] = "official_validation"

    with pytest.raises(ValueError, match="dev calibration"):
        results.aggregate_official_validation(reports, bootstrap_samples=10)


def test_seed_report_metadata_is_derived_from_training_provenance() -> None:
    results = _module()
    report = {
        "sample_order_sha256": "c" * 64,
        "confusions": [
            {
                "true_positive": 1,
                "false_positive": 0,
                "false_negative": 0,
                "true_negative": 1,
            }
        ],
    }
    config = {
        "model": {"name": "unet_efficientnet_b0"},
        "training": {"loss": "bce_dice"},
        "project": {"seed": 42},
    }
    provenance = {
        "source_commit": "a" * 40,
        "config_sha256": "1" * 64,
        "manifest_sha256": "b" * 64,
        "packages": {"torch": "2"},
        "cuda_version": "12",
        "cudnn_version": 9,
    }

    enriched = results.attach_seed_report_metadata(
        report,
        config=config,
        provenance=provenance,
        split="official_validation",
        checkpoint_sha256="d" * 64,
        bootstrap_samples=2000,
        bootstrap_seed=42,
    )

    assert enriched["model"] == "unet_efficientnet_b0"
    assert enriched["loss"] == "bce_dice"
    assert enriched["seed"] == 42
    assert enriched["source_commit"] == "a" * 40
    assert enriched["manifest_sha256"] == "b" * 64
    assert enriched["bootstrap"] == {"samples": 2000, "seed": 42, "cluster": "image"}
