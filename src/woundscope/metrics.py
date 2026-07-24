"""Transparent binary segmentation metrics and cluster bootstrap intervals."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Confusion:
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    def __add__(self, other: Confusion) -> Confusion:
        return Confusion(
            self.true_positive + other.true_positive,
            self.false_positive + other.false_positive,
            self.false_negative + other.false_negative,
            self.true_negative + other.true_negative,
        )


def confusion_from_arrays(prediction: np.ndarray, target: np.ndarray) -> Confusion:
    prediction = np.asarray(prediction, dtype=bool)
    target = np.asarray(target, dtype=bool)
    if prediction.shape != target.shape:
        raise ValueError(f"Prediction/target shape mismatch: {prediction.shape} != {target.shape}")
    return Confusion(
        true_positive=int(np.count_nonzero(prediction & target)),
        false_positive=int(np.count_nonzero(prediction & ~target)),
        false_negative=int(np.count_nonzero(~prediction & target)),
        true_negative=int(np.count_nonzero(~prediction & ~target)),
    )


def metrics_from_confusion(confusion: Confusion) -> dict[str, float]:
    tp = confusion.true_positive
    fp = confusion.false_positive
    fn = confusion.false_negative
    tn = confusion.true_negative

    def ratio(numerator: float, denominator: float, empty_value: float) -> float:
        return numerator / denominator if denominator else empty_value

    both_empty = tp + fp + fn == 0
    return {
        "dice": ratio(2 * tp, 2 * tp + fp + fn, 1.0 if both_empty else 0.0),
        "iou": ratio(tp, tp + fp + fn, 1.0 if both_empty else 0.0),
        "precision": ratio(tp, tp + fp, 1.0 if tp + fn == 0 else 0.0),
        "recall": ratio(tp, tp + fn, 1.0),
        "specificity": ratio(tn, tn + fp, 1.0),
    }


def evaluate_binary_batch(
    predictions: np.ndarray, targets: np.ndarray
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    predictions = np.asarray(predictions)
    targets = np.asarray(targets)
    if predictions.shape != targets.shape or predictions.ndim < 3:
        raise ValueError("Expected matching arrays shaped [N, ...]")
    rows: list[dict[str, Any]] = []
    total = Confusion(0, 0, 0, 0)
    for index, (prediction, target) in enumerate(zip(predictions, targets, strict=True)):
        confusion = confusion_from_arrays(prediction, target)
        total += confusion
        rows.append({"index": index, **asdict(confusion), **metrics_from_confusion(confusion)})
    return rows, metrics_from_confusion(total)


def summarize_image_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for metric in ("dice", "iou", "precision", "recall", "specificity"):
        values = np.asarray([float(row[metric]) for row in rows], dtype=np.float64)
        result[metric] = {
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            "q1": float(np.quantile(values, 0.25)),
            "q3": float(np.quantile(values, 0.75)),
        }
    return result


def cluster_bootstrap_ci(
    confusions: list[Confusion], samples: int = 2000, seed: int = 42
) -> dict[str, dict[str, float]]:
    if not confusions:
        raise ValueError("At least one image confusion is required")
    if samples <= 0:
        raise ValueError("Bootstrap sample count must be positive")
    randomizer = np.random.default_rng(seed)
    distributions = {name: [] for name in ("dice", "iou", "precision", "recall", "specificity")}
    for _ in range(samples):
        indices = randomizer.integers(0, len(confusions), size=len(confusions))
        total = Confusion(0, 0, 0, 0)
        for index in indices:
            total += confusions[int(index)]
        metrics = metrics_from_confusion(total)
        for name, value in metrics.items():
            distributions[name].append(value)
    return {
        name: {
            "lower": float(np.quantile(values, 0.025)),
            "median": float(np.quantile(values, 0.5)),
            "upper": float(np.quantile(values, 0.975)),
        }
        for name, values in distributions.items()
    }
