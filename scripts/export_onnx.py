"""Export a WoundScope checkpoint to fixed-spatial ONNX and verify parity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from woundscope.checkpointing import load_model_safetensors
from woundscope.config import load_config
from woundscope.exporting import export_onnx, onnx_parity
from woundscope.models import build_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    parser.add_argument("--image-size", type=int, default=512)
    args = parser.parse_args()
    config = load_config(args.config, args.model_config)
    model = build_model(config["model"], pretrained=False)
    load_model_safetensors(model, args.checkpoint)
    export_onnx(model, args.output, image_size=args.image_size)
    generator = torch.Generator().manual_seed(42)
    inputs = torch.rand((1, 3, args.image_size, args.image_size), generator=generator)
    parity = onnx_parity(model, args.output, inputs)
    print(json.dumps({"output": str(args.output.resolve()), "parity": parity}, indent=2))
    return 0 if parity["allclose"] and parity["masks_equal"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
