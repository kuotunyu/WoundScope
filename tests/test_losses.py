from __future__ import annotations

import pytest
import torch

from woundscope.losses import build_loss


@pytest.mark.parametrize("name", ["bce_dice", "focal_tversky"])
def test_loss_prefers_correct_prediction_and_has_finite_gradient(name: str) -> None:
    target = torch.tensor([[[[1.0, 0.0], [1.0, 0.0]]]])
    correct = torch.tensor([[[[8.0, -8.0], [8.0, -8.0]]]], requires_grad=True)
    wrong = -correct.detach()
    criterion = build_loss(name)

    correct_loss = criterion(correct, target)
    wrong_loss = criterion(wrong, target)
    correct_loss.backward()

    assert correct_loss.item() < wrong_loss.item()
    assert torch.isfinite(correct_loss)
    assert correct.grad is not None
    assert torch.all(torch.isfinite(correct.grad))


@pytest.mark.parametrize("name", ["bce_dice", "focal_tversky"])
def test_empty_mask_is_finite(name: str) -> None:
    target = torch.zeros((2, 1, 8, 8))
    logits = torch.zeros_like(target, requires_grad=True)

    loss = build_loss(name)(logits, target)
    loss.backward()

    assert torch.isfinite(loss)
    assert torch.all(torch.isfinite(logits.grad))


def test_unknown_loss_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported loss"):
        build_loss("made_up")
