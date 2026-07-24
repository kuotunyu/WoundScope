"""Model evaluation, calibration inputs, and report assembly."""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader

from woundscope.calibration import CalibrationArtifact, fit_temperature, threshold_sweep
from woundscope.checkpointing import file_sha256
from woundscope.config import config_hash
from woundscope.metrics import (
    Confusion,
    cluster_bootstrap_ci,
    evaluate_binary_batch,
    summarize_image_metrics,
)
from woundscope.uncertainty import tta_confidence


@torch.inference_mode()
def collect_logits(
    model: nn.Module,
    loader: DataLoader[dict[str, Any]],
    device: torch.device,
) -> tuple[Tensor, Tensor, list[str]]:
    model.eval()
    logits_batches: list[Tensor] = []
    target_batches: list[Tensor] = []
    sample_ids: list[str] = []
    for batch in loader:
        images = batch["image"].to(device)
        logits_batches.append(model(images).detach().cpu())
        target_batches.append(batch["mask"].detach().cpu())
        sample_ids.extend(str(sample_id) for sample_id in batch["sample_id"])
    return torch.cat(logits_batches), torch.cat(target_batches), sample_ids


@torch.inference_mode()
def collect_tta_logits(
    model: nn.Module,
    loader: DataLoader[dict[str, Any]],
    device: torch.device,
) -> tuple[Tensor, Tensor, Tensor, list[str]]:
    """Collect original and horizontally flipped/restored logits."""

    model.eval()
    original_batches: list[Tensor] = []
    flipped_batches: list[Tensor] = []
    target_batches: list[Tensor] = []
    sample_ids: list[str] = []
    for batch in loader:
        images = batch["image"].to(device)
        original_batches.append(model(images).detach().cpu())
        flipped = torch.flip(images, dims=(-1,))
        flipped_batches.append(torch.flip(model(flipped), dims=(-1,)).detach().cpu())
        target_batches.append(batch["mask"].detach().cpu())
        sample_ids.extend(str(sample_id) for sample_id in batch["sample_id"])
    return (
        torch.cat(original_batches),
        torch.cat(flipped_batches),
        torch.cat(target_batches),
        sample_ids,
    )


def fit_calibration_artifact(
    original_logits: Tensor,
    flipped_logits: Tensor,
    targets: Tensor,
    *,
    checkpoint_path: str | Path,
    config: dict[str, Any],
    confidence_quantile: float = 0.1,
) -> tuple[CalibrationArtifact, list[dict[str, Any]]]:
    """Fit dev-only temperature/threshold and derive the TTA confidence cutoff."""

    temperature = fit_temperature(original_logits, targets)
    probabilities = torch.sigmoid(original_logits.float() / temperature).numpy()[:, 0]
    target_array = targets.numpy()[:, 0] >= 0.5
    evaluation = config["evaluation"]
    threshold, sweep = threshold_sweep(
        probabilities,
        target_array,
        start=float(evaluation["threshold_start"]),
        stop=float(evaluation["threshold_stop"]),
        step=float(evaluation["threshold_step"]),
    )
    flipped_probabilities = torch.sigmoid(flipped_logits.float() / temperature).numpy()[:, 0]
    scores = [
        tta_confidence(
            original,
            flipped,
            threshold=threshold,
            cutoff=0.0,
            calibration_valid=True,
        ).score
        for original, flipped in zip(probabilities, flipped_probabilities, strict=True)
    ]
    cutoff = float(np.quantile(scores, confidence_quantile))
    return (
        CalibrationArtifact(
            temperature=temperature,
            threshold=threshold,
            confidence_cutoff=cutoff,
            checkpoint_sha256=file_sha256(checkpoint_path),
            config_hash=config_hash(config),
            split="dev",
        ),
        sweep,
    )


def write_image_metrics_csv(rows: list[dict[str, Any]], path: str | Path) -> None:
    if not rows:
        raise ValueError("Image metrics cannot be empty")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_metric_distributions(rows: list[dict[str, Any]], path: str | Path) -> None:
    """Persist all image-level metric distributions without selecting a best run."""

    if not rows:
        raise ValueError("Image metrics cannot be empty")
    metrics = ("dice", "iou", "precision", "recall", "specificity")
    figure, axes = plt.subplots(1, len(metrics), figsize=(15, 3), sharey=True)
    for axis, metric in zip(axes, metrics, strict=True):
        axis.hist([float(row[metric]) for row in rows], bins=20, range=(0, 1))
        axis.set_title(metric)
        axis.set_xlim(0, 1)
    axes[0].set_ylabel("image count")
    figure.tight_layout()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def evaluate_logits(
    logits: Tensor,
    targets: Tensor,
    sample_ids: list[str],
    *,
    threshold: float = 0.5,
    temperature: float = 1.0,
    bootstrap_samples: int = 2000,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    probabilities = torch.sigmoid(logits.float() / temperature).numpy()[:, 0]
    target_array = targets.numpy()[:, 0] >= 0.5
    rows, global_metrics = evaluate_binary_batch(probabilities >= threshold, target_array)
    for row, sample_id in zip(rows, sample_ids, strict=True):
        row["sample_id"] = sample_id
    confusions = [
        Confusion(
            row["true_positive"],
            row["false_positive"],
            row["false_negative"],
            row["true_negative"],
        )
        for row in rows
    ]
    return {
        "threshold": threshold,
        "temperature": temperature,
        "image_metrics": rows,
        "image_summary": summarize_image_metrics(rows),
        "global_metrics": global_metrics,
        "bootstrap_95_ci": cluster_bootstrap_ci(
            confusions, samples=bootstrap_samples, seed=bootstrap_seed
        ),
        "confusions": [asdict(confusion) for confusion in confusions],
    }
