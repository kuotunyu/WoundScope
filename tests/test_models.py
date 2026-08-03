from __future__ import annotations

import pytest
import torch

from woundscope.losses import build_loss
from woundscope.models import build_model


@pytest.mark.parametrize(
    "config",
    [
        {"family": "tiny_unet", "in_channels": 3, "out_channels": 1, "base_channels": 4},
        {
            "family": "unet",
            "encoder_name": "efficientnet-b0",
            "in_channels": 3,
            "out_channels": 1,
        },
        {"family": "segformer", "variant": "tiny", "in_channels": 3, "out_channels": 1},
    ],
)
def test_model_forward_returns_binary_logits_at_input_resolution(
    config: dict[str, object],
) -> None:
    torch.set_num_threads(1)
    model = build_model(config, pretrained=False).eval()
    inputs = torch.randn(1, 3, 64, 64)

    with torch.inference_mode():
        logits = model(inputs)

    assert logits.shape == (1, 1, 64, 64)
    assert torch.isfinite(logits).all()


def test_unknown_model_family_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported model family"):
        build_model({"family": "huge_unknown"}, pretrained=False)


def test_segformer_b0_checkpoint_loads_into_nonpretrained_evaluation_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transformers import SegformerConfig, SegformerForSemanticSegmentation

    def local_pretrained_model(*_args, **_kwargs):
        return SegformerForSemanticSegmentation(SegformerConfig(num_channels=3, num_labels=1))

    monkeypatch.setattr(
        SegformerForSemanticSegmentation,
        "from_pretrained",
        staticmethod(local_pretrained_model),
    )
    config = {
        "family": "segformer",
        "variant": "b0",
        "pretrained_name": "nvidia/mit-b0",
        "in_channels": 3,
        "out_channels": 1,
    }
    training_model = build_model(config, pretrained=True)
    evaluation_model = build_model(config, pretrained=False)

    evaluation_model.load_state_dict(training_model.state_dict())


def test_segformer_without_variant_defaults_to_production_b0() -> None:
    model = build_model(
        {"family": "segformer", "in_channels": 3, "out_channels": 1},
        pretrained=False,
    )

    assert sum(parameter.numel() for parameter in model.parameters()) == 3_714_401


@pytest.mark.parametrize(
    "config",
    [
        {
            "family": "unet",
            "encoder_name": "efficientnet-b0",
            "in_channels": 3,
            "out_channels": 1,
        },
        {"family": "segformer", "variant": "tiny", "in_channels": 3, "out_channels": 1},
    ],
)
def test_release_models_complete_cpu_optimizer_step(config: dict[str, object]) -> None:
    torch.set_num_threads(1)
    model = build_model(config, pretrained=False).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    inputs = torch.randn(2, 3, 64, 64)
    targets = torch.zeros(2, 1, 64, 64)
    targets[:, :, 16:48, 16:48] = 1

    loss = build_loss("bce_dice")(model(inputs), targets)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()

    assert torch.isfinite(loss)
    assert any(parameter.grad is not None for parameter in model.parameters())
