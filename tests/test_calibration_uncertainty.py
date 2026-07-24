from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from woundscope.calibration import CalibrationArtifact, fit_temperature, threshold_sweep
from woundscope.uncertainty import tta_confidence


def test_temperature_is_positive_and_finite() -> None:
    logits = torch.tensor([[[[3.0, -2.0], [1.0, -1.0]]]])
    targets = torch.tensor([[[[1.0, 0.0], [1.0, 0.0]]]])

    temperature = fit_temperature(logits, targets, max_iter=10)

    assert np.isfinite(temperature)
    assert 0.05 <= temperature <= 20.0


def test_threshold_sweep_selects_best_and_tie_nearest_half() -> None:
    probabilities = np.array([[[0.9, 0.4], [0.7, 0.1]]])
    targets = np.array([[[1, 0], [1, 0]]], dtype=bool)

    threshold, rows = threshold_sweep(probabilities, targets, start=0.3, stop=0.7, step=0.1)

    assert threshold == pytest.approx(0.5)
    assert rows


def test_calibration_artifact_round_trip(tmp_path: Path) -> None:
    artifact = CalibrationArtifact(1.2, 0.46, 0.65, "abc", "def")
    path = tmp_path / "calibration.json"

    artifact.save(path)

    assert CalibrationArtifact.load(path) == artifact


def test_tta_confidence_flags_missing_calibration_and_empty_prediction() -> None:
    probability = np.full((8, 8), 0.01)

    result = tta_confidence(
        probability,
        probability,
        threshold=0.5,
        cutoff=0.5,
        calibration_valid=False,
    )

    assert result.low_confidence
    assert "empty_prediction" in result.reasons
    assert "calibration_metadata_missing_or_incompatible" in result.reasons


def test_tta_confidence_accepts_stable_confident_prediction() -> None:
    probability = np.full((8, 8), 0.01)
    probability[2:6, 2:6] = 0.99

    result = tta_confidence(probability, probability, threshold=0.5, cutoff=0.5)

    assert not result.low_confidence
    assert result.score > 0.9
