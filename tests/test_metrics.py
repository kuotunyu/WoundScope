from __future__ import annotations

import numpy as np

from woundscope.metrics import (
    Confusion,
    cluster_bootstrap_ci,
    confusion_from_arrays,
    evaluate_binary_batch,
    metrics_from_confusion,
    summarize_image_metrics,
)


def test_known_confusion_and_metrics() -> None:
    prediction = np.array([[1, 1], [0, 0]], dtype=bool)
    target = np.array([[1, 0], [1, 0]], dtype=bool)

    confusion = confusion_from_arrays(prediction, target)
    metrics = metrics_from_confusion(confusion)

    assert confusion == Confusion(1, 1, 1, 1)
    assert metrics == {
        "dice": 0.5,
        "iou": 1 / 3,
        "precision": 0.5,
        "recall": 0.5,
        "specificity": 0.5,
    }


def test_empty_empty_is_perfect_not_nan() -> None:
    metrics = metrics_from_confusion(Confusion(0, 0, 0, 16))

    assert all(value == 1.0 for value in metrics.values())


def test_batch_summary_and_global_are_both_available() -> None:
    predictions = np.array([np.zeros((2, 2)), np.ones((2, 2))], dtype=bool)
    targets = np.array([np.zeros((2, 2)), np.ones((2, 2))], dtype=bool)

    rows, global_metrics = evaluate_binary_batch(predictions, targets)
    summary = summarize_image_metrics(rows)

    assert len(rows) == 2
    assert global_metrics["dice"] == 1.0
    assert summary["dice"]["mean"] == 1.0


def test_cluster_bootstrap_is_reproducible() -> None:
    confusions = [Confusion(5, 1, 2, 20), Confusion(3, 2, 1, 10)]

    first = cluster_bootstrap_ci(confusions, samples=100, seed=42)
    second = cluster_bootstrap_ci(confusions, samples=100, seed=42)

    assert first == second
    assert first["dice"]["lower"] <= first["dice"]["upper"]
