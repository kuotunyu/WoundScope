"""Generate a local five-category error gallery from locked evaluation outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from woundscope.calibration import CalibrationArtifact
from woundscope.config import load_config
from woundscope.dataset import read_manifest
from woundscope.inference import OnnxPredictor, create_overlay
from woundscope.reporting import select_error_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--challenge-dir", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--selector", default="official_validation")
    parser.add_argument("--output", type=Path, default=Path("reports/error_gallery"))
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    config = load_config(args.config)
    selected_rows = [
        row
        for row in read_manifest(args.manifest)
        if row["internal_split"] == args.selector or row["split"] == args.selector
    ]
    manifest = {row["sample_id"]: row for row in selected_rows}
    if len(manifest) != len(selected_rows):
        raise RuntimeError("Sample IDs are not unique within the selected gallery split")
    with args.metrics.open("r", encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    enriched = []
    for record in records:
        row = manifest[record["sample_id"]]
        with Image.open(args.challenge_dir / row["image_relpath"]) as source:
            brightness = float(np.asarray(source.convert("L"), dtype=np.float32).mean())
        total = sum(
            int(record[key])
            for key in ("true_positive", "false_positive", "false_negative", "true_negative")
        )
        enriched.append(
            {
                **record,
                "dice": float(record["dice"]),
                "target_ratio": (int(record["true_positive"]) + int(record["false_negative"]))
                / total,
                "false_positive_ratio": int(record["false_positive"]) / total,
                "brightness": brightness,
                "manifest_row": row,
            }
        )
    selected = select_error_cases(enriched)
    predictor = OnnxPredictor(
        args.model,
        CalibrationArtifact.load(args.calibration),
        device=args.device,
        image_size=int(config["data"]["image_size"]),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for category, record in selected.items():
        row = record["manifest_row"]
        with Image.open(args.challenge_dir / row["image_relpath"]) as source:
            image = source.convert("RGB")
        with Image.open(args.challenge_dir / row["mask_relpath"]) as source:
            target_mask = np.asarray(source.convert("L")) >= 128
        result = predictor.predict(image)
        target_overlay = create_overlay(image, target_mask)
        prediction_overlay = create_overlay(image, result.mask)
        panel = Image.new("RGB", (image.width * 3, image.height))
        panel.paste(image, (0, 0))
        panel.paste(target_overlay, (image.width, 0))
        panel.paste(prediction_overlay, (2 * image.width, 0))
        panel.save(args.output / f"{category}_{record['sample_id']}_original_gt_prediction.png")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
