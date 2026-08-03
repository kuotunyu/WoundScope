"""Calibrate on internal dev or evaluate a frozen checkpoint on an approved split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from woundscope.calibration import CalibrationArtifact
from woundscope.checkpointing import file_sha256, load_model_safetensors
from woundscope.config import config_hash, load_config
from woundscope.dataset import build_dataloader
from woundscope.evaluation import (
    collect_tta_logits,
    evaluate_logits,
    fit_calibration_artifact,
    write_image_metrics_csv,
    write_metric_distributions,
)
from woundscope.models import build_model
from woundscope.provenance import write_json_atomic
from woundscope.results import attach_seed_report_metadata
from woundscope.training import resolve_device


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--mode-config", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--selector", choices=("dev", "official_validation"), default="dev")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--fit-calibration", action="store_true")
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    args = parser.parse_args()
    if args.fit_calibration != (args.selector == "dev"):
        raise SystemExit("Calibration fitting is mandatory on dev and forbidden on validation")

    config = load_config(args.config, args.model_config, args.mode_config, args.overrides)
    provenance_path = args.checkpoint.parent / "provenance.json"
    if not provenance_path.is_file():
        raise SystemExit("Training provenance is required for evaluation")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("config_sha256") != config_hash(config):
        raise SystemExit(
            "Resolved evaluation config does not match training provenance; pass the same --set overrides"
        )
    data_root = Path(config["data"]["root"])
    challenge_dir = (
        data_root / config["data"]["raw_subdirectory"] / config["data"]["source_subdirectory"]
    )
    manifest = data_root / config["data"]["manifest_subdirectory"] / "data_manifest.csv"
    loader = build_dataloader(
        challenge_dir,
        manifest,
        args.selector,
        image_size=int(config["data"]["image_size"]),
        batch_size=int(config["training"]["batch_size"]),
        train=False,
        num_workers=int(config["training"]["num_workers"]),
    )
    model = build_model(config["model"], pretrained=False)
    load_model_safetensors(model, args.checkpoint)
    device = resolve_device(args.device)
    model.to(device)
    original, flipped, targets, sample_ids = collect_tta_logits(model, loader, device)
    sweep = None
    if args.fit_calibration:
        calibration, sweep = fit_calibration_artifact(
            original,
            flipped,
            targets,
            checkpoint_path=args.checkpoint,
            config=config,
            confidence_quantile=float(config["evaluation"]["confidence_quantile"]),
        )
        calibration.save(args.calibration)
    else:
        calibration = CalibrationArtifact.load(args.calibration)
        if calibration.checkpoint_sha256 != file_sha256(args.checkpoint):
            raise SystemExit("Calibration checkpoint hash does not match the evaluated checkpoint")
        if calibration.config_hash != config_hash(config):
            raise SystemExit(
                "Calibration config hash does not match the resolved evaluation config"
            )
    report = evaluate_logits(
        original,
        targets,
        sample_ids,
        flipped_logits=flipped,
        threshold=calibration.threshold,
        temperature=calibration.temperature,
        confidence_cutoff=calibration.confidence_cutoff,
        bootstrap_samples=int(config["evaluation"]["bootstrap_samples"]),
        bootstrap_seed=int(config["evaluation"]["bootstrap_seed"]),
    )
    report = attach_seed_report_metadata(
        report,
        config=config,
        provenance=provenance,
        split=args.selector,
        checkpoint_sha256=file_sha256(args.checkpoint),
        bootstrap_samples=int(config["evaluation"]["bootstrap_samples"]),
        bootstrap_seed=int(config["evaluation"]["bootstrap_seed"]),
    )
    report["status"] = "completed"
    report["calibration"] = {
        "temperature": calibration.temperature,
        "threshold": calibration.threshold,
        "confidence_cutoff": calibration.confidence_cutoff,
        "source_split": calibration.split,
    }
    if sweep is not None:
        report["threshold_sweep"] = sweep
    args.output.mkdir(parents=True, exist_ok=True)
    image_metrics = report.pop("image_metrics")
    write_image_metrics_csv(image_metrics, args.output / "per_image_metrics.csv")
    write_metric_distributions(image_metrics, args.output / "metric_distributions.png")
    write_json_atomic(report, args.output / "results.json")
    print(args.output / "results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
