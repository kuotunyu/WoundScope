"""Run WoundScope prediction for one image using ONNX or safetensors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from woundscope.calibration import CalibrationArtifact
from woundscope.checkpointing import load_model_safetensors
from woundscope.config import load_config
from woundscope.inference import OnnxPredictor, TorchPredictor, create_overlay
from woundscope.models import build_model
from woundscope.training import resolve_device


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model", type=Path, required=True, help="ONNX model path")
    parser.add_argument("--model-config", type=Path, default=None)
    parser.add_argument("--calibration", type=Path, default=None)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    calibration = (
        CalibrationArtifact.load(args.calibration) if args.calibration is not None else None
    )
    config = load_config(args.config, args.model_config)
    if args.model.suffix.casefold() == ".onnx":
        predictor = OnnxPredictor(
            args.model,
            calibration,
            device=args.device,
            image_size=int(config["data"]["image_size"]),
        )
    else:
        if args.model_config is None:
            raise SystemExit("--model-config is required for a PyTorch safetensors checkpoint")
        model = build_model(config["model"], pretrained=False)
        load_model_safetensors(model, args.model)
        predictor = TorchPredictor(
            model,
            calibration,
            device=str(resolve_device(args.device)),
            image_size=int(config["data"]["image_size"]),
        )
    with Image.open(args.input) as source:
        image = source.convert("RGB")
    result = predictor.predict(image)
    args.output.mkdir(parents=True, exist_ok=True)
    Image.fromarray((result.mask * 255).astype(np.uint8), mode="L").save(
        args.output / f"{args.input.stem}_mask.png"
    )
    create_overlay(image, result.mask).save(args.output / f"{args.input.stem}_overlay.png")
    summary = {
        "input": str(args.input.resolve()),
        "wound_pixel_ratio": result.wound_pixel_ratio,
        "confidence": result.confidence.score,
        "low_confidence": result.confidence.low_confidence,
        "review_reasons": result.confidence.reasons,
        "inference_seconds": result.inference_seconds,
    }
    (args.output / f"{args.input.stem}_result.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
