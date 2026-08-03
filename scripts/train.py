"""Train a WoundScope model from the validated, gitignored FUSeg manifest."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import yaml

from woundscope.config import load_config
from woundscope.dataset import build_dataloader
from woundscope.models import build_model
from woundscope.protocol import read_data_summary, resolve_cross_split_policy
from woundscope.provenance import build_provenance, write_json_atomic
from woundscope.training import train_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--mode-config", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--stop-after-epoch",
        type=int,
        default=None,
        help="Persist and stop after N completed epochs so quick mode can prove resume.",
    )
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument(
        "--cross-split-policy",
        choices=("error", "exclude_train"),
        default="error",
        help="Default refuses to train; exclude_train removes exact train copies.",
    )
    parser.add_argument("--set", dest="overrides", action="append", default=[])
    args = parser.parse_args()

    config = load_config(args.config, args.model_config, args.mode_config, args.overrides)
    data_root = Path(config["data"]["root"])
    challenge_dir = (
        data_root / config["data"]["raw_subdirectory"] / config["data"]["source_subdirectory"]
    )
    manifest = data_root / config["data"]["manifest_subdirectory"] / "data_manifest.csv"
    summary_path = manifest.with_name("data_summary.json")
    exclusions, policy_record = resolve_cross_split_policy(
        read_data_summary(summary_path), args.cross_split_policy
    )
    mode_name = str(config["mode"]["name"])
    run_dir = args.run_dir or (
        Path(config["artifacts"]["root"])
        / "runs"
        / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{config['model']['name']}_{mode_name}_seed{config['project']['seed']}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_config_path = run_dir / "config.resolved.yaml"
    temporary_config_path = resolved_config_path.with_suffix(resolved_config_path.suffix + ".tmp")
    temporary_config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    temporary_config_path.replace(resolved_config_path)
    write_json_atomic(policy_record, run_dir / "cross_split_policy.json")
    common = {
        "challenge_dir": challenge_dir,
        "manifest_path": manifest,
        "image_size": int(config["data"]["image_size"]),
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": int(config["training"]["num_workers"]),
    }
    train_loader = build_dataloader(
        **common,
        selector="train",
        train=True,
        limit=config["data"].get("max_train_samples"),
        excluded_keys=exclusions,
    )
    dev_loader = build_dataloader(
        **common,
        selector="dev",
        train=False,
        limit=config["data"].get("max_dev_samples"),
        excluded_keys=exclusions,
    )
    model = build_model(config["model"], pretrained=not args.no_pretrained)
    provenance = build_provenance(
        config, manifest, seed=int(config["project"]["seed"]), device=args.device
    )
    provenance["cross_split_policy"] = policy_record
    write_json_atomic(provenance, run_dir / "provenance.json")
    result = train_model(
        model,
        train_loader,
        dev_loader,
        config,
        run_dir,
        manifest_hash=provenance["manifest_sha256"],
        device=args.device,
        resume=args.resume,
        stop_after_epoch=args.stop_after_epoch,
    )
    provenance["best_checkpoint_sha256"] = result["best_checkpoint_sha256"]
    provenance["last_checkpoint_sha256"] = result["last_checkpoint_sha256"]
    write_json_atomic(provenance, run_dir / "provenance.json")
    print(yaml.safe_dump(result, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
