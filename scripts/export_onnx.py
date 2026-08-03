"""Export a WoundScope checkpoint to fixed-spatial ONNX and verify parity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from woundscope.calibration import CalibrationArtifact
from woundscope.checkpointing import file_sha256, load_model_safetensors
from woundscope.config import config_hash, load_config
from woundscope.exporting import export_onnx, onnx_parity
from woundscope.models import build_model
from woundscope.provenance import write_json_atomic


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--mode-config", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    parser.add_argument("--image-size", type=int, default=512)
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    args = parser.parse_args()
    config = load_config(args.config, args.model_config, args.mode_config, args.overrides)
    model = build_model(config["model"], pretrained=False)
    load_model_safetensors(model, args.checkpoint)
    export_onnx(model, args.output, image_size=args.image_size)
    threshold = 0.5
    temperature = 1.0
    if args.calibration is not None:
        calibration = CalibrationArtifact.load(args.calibration)
        if calibration.checkpoint_sha256 != file_sha256(args.checkpoint):
            raise SystemExit("Calibration checkpoint hash does not match ONNX export checkpoint")
        if calibration.config_hash != config_hash(config):
            raise SystemExit("Calibration config hash does not match ONNX export config")
        threshold = calibration.threshold
        temperature = calibration.temperature
    generator = torch.Generator().manual_seed(42)
    inputs = torch.rand((1, 3, args.image_size, args.image_size), generator=generator)
    parity = onnx_parity(
        model,
        args.output,
        inputs,
        threshold=threshold,
        temperature=temperature,
    )
    report = {
        "status": "completed" if parity["parity_passed"] else "failed",
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "onnx_sha256": file_sha256(args.output),
        "config_sha256": config_hash(config),
        "threshold": threshold,
        "temperature": temperature,
        "parity": parity,
    }
    if args.report is not None:
        write_json_atomic(report, args.report)
    print(json.dumps(report, indent=2))
    return 0 if parity["parity_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
