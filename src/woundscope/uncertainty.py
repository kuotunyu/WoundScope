"""Transparent two-view TTA confidence and review policy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ConfidenceResult:
    score: float
    entropy_certainty: float
    tta_agreement: float
    low_confidence: bool
    reasons: tuple[str, ...]


def _soft_dice(left: np.ndarray, right: np.ndarray, smooth: float = 1e-6) -> float:
    numerator = 2 * float(np.sum(left * right)) + smooth
    denominator = float(np.sum(left) + np.sum(right)) + smooth
    return numerator / denominator


def tta_confidence(
    original_probability: np.ndarray,
    flipped_probability_restored: np.ndarray,
    *,
    threshold: float,
    cutoff: float,
    calibration_valid: bool = True,
) -> ConfidenceResult:
    original = np.asarray(original_probability, dtype=np.float64)
    flipped = np.asarray(flipped_probability_restored, dtype=np.float64)
    if original.shape != flipped.shape:
        raise ValueError("TTA probability arrays must have identical shapes")
    mean_probability = np.clip((original + flipped) / 2, 1e-7, 1 - 1e-7)
    candidate = mean_probability >= 0.1
    if np.any(candidate):
        entropy = -(
            mean_probability[candidate] * np.log(mean_probability[candidate])
            + (1 - mean_probability[candidate]) * np.log(1 - mean_probability[candidate])
        )
        entropy_certainty = float(1 - np.mean(entropy) / np.log(2))
    else:
        entropy_certainty = 0.0
    agreement = _soft_dice(original, flipped)
    score = float(np.clip(0.5 * entropy_certainty + 0.5 * agreement, 0.0, 1.0))
    prediction_empty = not np.any(mean_probability >= threshold)
    reasons: list[str] = []
    if not calibration_valid:
        reasons.append("calibration_metadata_missing_or_incompatible")
    if prediction_empty:
        reasons.append("empty_prediction")
    if score < cutoff:
        reasons.append("confidence_below_dev_cutoff")
    return ConfidenceResult(
        score=score,
        entropy_certainty=entropy_certainty,
        tta_agreement=agreement,
        low_confidence=bool(reasons),
        reasons=tuple(reasons),
    )
