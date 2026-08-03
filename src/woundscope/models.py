"""Small binary segmentation model factory."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F
from torch import Tensor, nn


class TinyUNet(nn.Module):
    """A deterministic small U-Net used for offline tests and vertical-slice smoke runs."""

    def __init__(self, in_channels: int = 3, out_channels: int = 1, base_channels: int = 8) -> None:
        super().__init__()

        def block(source: int, target: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(source, target, 3, padding=1),
                nn.ReLU(inplace=True),
                nn.Conv2d(target, target, 3, padding=1),
                nn.ReLU(inplace=True),
            )

        self.encoder1 = block(in_channels, base_channels)
        self.encoder2 = block(base_channels, base_channels * 2)
        self.bottleneck = block(base_channels * 2, base_channels * 4)
        self.decoder2 = block(base_channels * 4 + base_channels * 2, base_channels * 2)
        self.decoder1 = block(base_channels * 2 + base_channels, base_channels)
        self.output = nn.Conv2d(base_channels, out_channels, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, inputs: Tensor) -> Tensor:
        encoder1 = self.encoder1(inputs)
        encoder2 = self.encoder2(self.pool(encoder1))
        bottleneck = self.bottleneck(self.pool(encoder2))
        decoder2 = F.interpolate(
            bottleneck, size=encoder2.shape[-2:], mode="bilinear", align_corners=False
        )
        decoder2 = self.decoder2(torch.cat([decoder2, encoder2], dim=1))
        decoder1 = F.interpolate(
            decoder2, size=encoder1.shape[-2:], mode="bilinear", align_corners=False
        )
        decoder1 = self.decoder1(torch.cat([decoder1, encoder1], dim=1))
        return self.output(decoder1)


class _SegFormerBinaryWrapper(nn.Module):
    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, inputs: Tensor) -> Tensor:
        logits = self.model(pixel_values=inputs).logits
        return F.interpolate(logits, size=inputs.shape[-2:], mode="bilinear", align_corners=False)


def _build_segformer(config: dict[str, Any], pretrained: bool) -> nn.Module:
    from transformers import SegformerConfig, SegformerForSemanticSegmentation

    variant = str(config.get("variant", "b0")).casefold()
    if pretrained:
        if variant != "b0":
            raise ValueError("Pretrained SegFormer is only supported for the b0 variant")
        model = SegformerForSemanticSegmentation.from_pretrained(
            config.get("pretrained_name", "nvidia/mit-b0"),
            num_labels=1,
            ignore_mismatched_sizes=True,
        )
    elif variant == "b0":
        b0_config = SegformerConfig(
            num_channels=int(config.get("in_channels", 3)),
            num_labels=int(config.get("out_channels", 1)),
            num_encoder_blocks=4,
            depths=[2, 2, 2, 2],
            hidden_sizes=[32, 64, 160, 256],
            decoder_hidden_size=256,
            num_attention_heads=[1, 2, 5, 8],
            sr_ratios=[8, 4, 2, 1],
            patch_sizes=[7, 3, 3, 3],
            strides=[4, 2, 2, 2],
            mlp_ratios=[4, 4, 4, 4],
        )
        model = SegformerForSemanticSegmentation(b0_config)
    elif variant == "tiny":
        test_config = SegformerConfig(
            num_channels=int(config.get("in_channels", 3)),
            num_labels=int(config.get("out_channels", 1)),
            depths=[1, 1, 1, 1],
            hidden_sizes=[8, 16, 32, 64],
            decoder_hidden_size=32,
            num_attention_heads=[1, 1, 2, 4],
            sr_ratios=[8, 4, 2, 1],
            patch_sizes=[7, 3, 3, 3],
            strides=[4, 2, 2, 2],
        )
        model = SegformerForSemanticSegmentation(test_config)
    else:
        raise ValueError(f"Unsupported SegFormer variant: {variant}")
    return _SegFormerBinaryWrapper(model)


def build_model(config: dict[str, Any], *, pretrained: bool = True) -> nn.Module:
    family = str(config.get("family", config.get("name", ""))).casefold()
    if family == "tiny_unet":
        return TinyUNet(
            in_channels=int(config.get("in_channels", 3)),
            out_channels=int(config.get("out_channels", 1)),
            base_channels=int(config.get("base_channels", 8)),
        )
    if family == "unet":
        import segmentation_models_pytorch as smp

        weights = config.get("encoder_weights", "imagenet") if pretrained else None
        return smp.Unet(
            encoder_name=str(config.get("encoder_name", "efficientnet-b0")),
            encoder_weights=weights,
            in_channels=int(config.get("in_channels", 3)),
            classes=int(config.get("out_channels", 1)),
        )
    if family == "segformer":
        return _build_segformer(config, pretrained)
    raise ValueError(f"Unsupported model family: {family}")
