"""Post-hoc temperature, threshold, and calibration artifact handling."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor

from woundscope.metrics import confusion_from_arrays, metrics_from_confusion


@dataclass(frozen=True)
class CalibrationArtifact:
    temperature: float
    threshold: float
    confidence_cutoff: float
    checkpoint_sha256: str
    config_hash: str
    split: str = "dev"

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: str | Path) -> CalibrationArtifact:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)


def fit_temperature(logits: Tensor, targets: Tensor, max_iter: int = 50) -> float:
    logits = logits.detach().float().cpu()
    targets = targets.detach().float().cpu()
    log_temperature = torch.nn.Parameter(torch.zeros(()))
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.1, max_iter=max_iter)

    def closure() -> Tensor:
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 20.0)
        loss = F.binary_cross_entropy_with_logits(logits / temperature, targets)
        loss.backward()
        return loss

    optimizer.step(closure)
    return float(log_temperature.detach().exp().clamp(0.05, 20.0))


def threshold_sweep(
    probabilities: np.ndarray,
    targets: np.ndarray,
    start: float = 0.1,
    stop: float = 0.9,
    step: float = 0.02,
) -> tuple[float, list[dict[str, Any]]]:
    probabilities = np.asarray(probabilities, dtype=np.float64)
    targets = np.asarray(targets, dtype=bool)
    if probabilities.shape != targets.shape:
        raise ValueError("Probability and target arrays must have identical shapes")
    thresholds = np.arange(start, stop + step / 2, step)
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        image_dice = []
        for probability, target in zip(probabilities, targets, strict=True):
            confusion = confusion_from_arrays(probability >= threshold, target)
            image_dice.append(metrics_from_confusion(confusion)["dice"])
        rows.append({"threshold": float(threshold), "mean_image_dice": float(np.mean(image_dice))})
    best_score = max(row["mean_image_dice"] for row in rows)
    candidates = [row for row in rows if np.isclose(row["mean_image_dice"], best_score)]
    best = min(candidates, key=lambda row: (abs(row["threshold"] - 0.5), row["threshold"]))
    return float(best["threshold"]), rows
