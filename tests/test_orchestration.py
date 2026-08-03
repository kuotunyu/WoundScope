from __future__ import annotations

import importlib

import pytest


def _module():
    return importlib.import_module("woundscope.orchestration")


def test_quick_and_comparison_matrices_are_fixed() -> None:
    orchestration = _module()

    quick = orchestration.build_quick_specs()
    comparison = orchestration.build_comparison_specs()

    expected = {
        ("unet_efficientnet_b0", "bce_dice", 42),
        ("unet_efficientnet_b0", "focal_tversky", 42),
        ("segformer_b0", "bce_dice", 42),
        ("segformer_b0", "focal_tversky", 42),
    }
    assert {(run.model_name, run.loss, run.seed) for run in quick} == expected
    assert {(run.model_name, run.loss, run.seed) for run in comparison} == expected
    assert {run.mode for run in quick} == {"quick"}
    assert {run.mode for run in comparison} == {"full"}


def test_loss_selection_uses_locked_metrics_and_bce_final_tie_break() -> None:
    orchestration = _module()
    source_commit = "a" * 40
    candidates = [
        {
            "model": "unet_efficientnet_b0",
            "loss": "bce_dice",
            "split": "dev",
            "source_commit": source_commit,
            "input_artifact_sha256": "1" * 64,
            "metrics": {"mean_image_dice": 0.80, "global_dice": 0.81, "recall": 0.70},
        },
        {
            "model": "unet_efficientnet_b0",
            "loss": "focal_tversky",
            "split": "dev",
            "source_commit": source_commit,
            "input_artifact_sha256": "2" * 64,
            "metrics": {"mean_image_dice": 0.80, "global_dice": 0.81, "recall": 0.70},
        },
        {
            "model": "segformer_b0",
            "loss": "bce_dice",
            "split": "dev",
            "source_commit": source_commit,
            "input_artifact_sha256": "3" * 64,
            "metrics": {"mean_image_dice": 0.75, "global_dice": 0.82, "recall": 0.77},
        },
        {
            "model": "segformer_b0",
            "loss": "focal_tversky",
            "split": "dev",
            "source_commit": source_commit,
            "input_artifact_sha256": "4" * 64,
            "metrics": {"mean_image_dice": 0.76, "global_dice": 0.70, "recall": 0.60},
        },
    ]

    selection = orchestration.select_losses(candidates, source_commit)

    assert selection["selection_order"] == [
        "mean_image_dice",
        "global_dice",
        "recall",
        "prefer_bce_dice",
    ]
    assert selection["models"]["unet_efficientnet_b0"]["selected_loss"] == "bce_dice"
    assert selection["models"]["segformer_b0"]["selected_loss"] == "focal_tversky"
    assert selection["official_validation_used"] is False
    assert selection["source_commit"] == source_commit


def test_loss_selection_rejects_official_validation_inputs() -> None:
    orchestration = _module()
    candidate = {
        "model": "unet_efficientnet_b0",
        "loss": "bce_dice",
        "split": "official_validation",
        "source_commit": "a" * 40,
        "input_artifact_sha256": "1" * 64,
        "metrics": {"mean_image_dice": 0.8, "global_dice": 0.8, "recall": 0.8},
    }

    with pytest.raises(ValueError, match="internal dev"):
        orchestration.select_losses([candidate], "a" * 40)


def test_seed42_reuse_requires_all_hashes_and_provenance() -> None:
    orchestration = _module()
    final_spec = orchestration.RunSpec(
        stage="final",
        mode="full",
        model_name="unet_efficientnet_b0",
        model_config="configs/models/unet_efficientnet_b0.yaml",
        loss="bce_dice",
        seed=42,
        config_sha256="c" * 64,
        manifest_sha256="b" * 64,
    )
    candidate = {
        "status": "completed",
        "model": "unet_efficientnet_b0",
        "loss": "bce_dice",
        "seed": 42,
        "config_sha256": "c" * 64,
        "manifest_sha256": "b" * 64,
        "checkpoint_sha256": "d" * 64,
        "source_commit": "a" * 40,
    }

    assert orchestration.verify_seed42_reuse(candidate, final_spec)["reusable"] is True

    candidate["manifest_sha256"] = "different"
    rejected = orchestration.verify_seed42_reuse(candidate, final_spec)
    assert rejected["reusable"] is False
    assert "manifest_sha256" in rejected["mismatches"]
