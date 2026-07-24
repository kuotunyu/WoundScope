"""Binary segmentation losses with explicit foreground-imbalance handling."""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor, nn


def _flatten_batch(tensor: Tensor) -> Tensor:
    return tensor.reshape(tensor.shape[0], -1)


class DiceLoss(nn.Module):
    def __init__(self, smooth: float = 1e-6) -> None:
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        probabilities = _flatten_batch(torch.sigmoid(logits))
        targets = _flatten_batch(targets.float())
        intersection = (probabilities * targets).sum(dim=1)
        denominator = probabilities.sum(dim=1) + targets.sum(dim=1)
        score = (2 * intersection + self.smooth) / (denominator + self.smooth)
        return 1 - score.mean()


class FocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.75, gamma: float = 2.0) -> None:
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        targets = targets.float()
        binary_cross_entropy = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probabilities = torch.sigmoid(logits)
        probability_correct = targets * probabilities + (1 - targets) * (1 - probabilities)
        alpha_weight = targets * self.alpha + (1 - targets) * (1 - self.alpha)
        return (
            alpha_weight * (1 - probability_correct).pow(self.gamma) * binary_cross_entropy
        ).mean()


class TverskyLoss(nn.Module):
    def __init__(self, alpha_fp: float = 0.3, beta_fn: float = 0.7, smooth: float = 1e-6) -> None:
        super().__init__()
        self.alpha_fp = alpha_fp
        self.beta_fn = beta_fn
        self.smooth = smooth

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        probabilities = _flatten_batch(torch.sigmoid(logits))
        targets = _flatten_batch(targets.float())
        true_positive = (probabilities * targets).sum(dim=1)
        false_positive = (probabilities * (1 - targets)).sum(dim=1)
        false_negative = ((1 - probabilities) * targets).sum(dim=1)
        score = (true_positive + self.smooth) / (
            true_positive
            + self.alpha_fp * false_positive
            + self.beta_fn * false_negative
            + self.smooth
        )
        return 1 - score.mean()


class BCEDiceLoss(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.dice = DiceLoss()

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        bce = F.binary_cross_entropy_with_logits(logits, targets.float())
        return 0.5 * bce + 0.5 * self.dice(logits, targets)


class FocalTverskyLoss(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.focal = FocalLoss(alpha=0.75, gamma=2.0)
        self.tversky = TverskyLoss(alpha_fp=0.3, beta_fn=0.7)

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        return 0.5 * self.focal(logits, targets) + 0.5 * self.tversky(logits, targets)


def build_loss(name: str) -> nn.Module:
    normalized = name.casefold().replace("-", "_")
    if normalized == "bce_dice":
        return BCEDiceLoss()
    if normalized == "focal_tversky":
        return FocalTverskyLoss()
    raise ValueError(f"Unsupported loss: {name}")
