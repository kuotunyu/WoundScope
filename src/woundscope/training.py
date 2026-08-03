"""Small, resumable PyTorch training loop with per-epoch persistence."""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter

from woundscope.checkpointing import (
    capture_rng_state,
    file_sha256,
    load_model_safetensors,
    load_trainer_state,
    restore_rng_state,
    save_model_safetensors,
    save_trainer_state,
)
from woundscope.config import config_hash
from woundscope.losses import build_loss
from woundscope.provenance import write_json_atomic


def seed_everything(seed: int, deterministic_warn_only: bool = True) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=deterministic_warn_only)


def resolve_device(requested: str) -> torch.device:
    normalized = requested.casefold()
    if normalized == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if normalized == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    if normalized not in {"cpu", "cuda"}:
        raise ValueError(f"Unsupported device: {requested}")
    return torch.device(normalized)


def _write_history(history: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)
    temporary.replace(path)


def _run_epoch(
    model: nn.Module,
    loader: DataLoader[dict[str, Any]],
    criterion: nn.Module,
    device: torch.device,
    *,
    optimizer: torch.optim.Optimizer | None,
    scaler: torch.amp.GradScaler,
    accumulation: int,
    amp: bool,
) -> tuple[float, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_dice = 0.0
    total_images = 0
    if training:
        optimizer.zero_grad(set_to_none=True)
    for batch_index, batch in enumerate(loader):
        images = batch["image"].to(device)
        targets = batch["mask"].to(device)
        with (
            torch.set_grad_enabled(training),
            torch.amp.autocast(device_type=device.type, enabled=amp),
        ):
            logits = model(images)
            loss = criterion(logits, targets)
        if training:
            scaler.scale(loss / accumulation).backward()
            should_step = (batch_index + 1) % accumulation == 0 or batch_index + 1 == len(loader)
            if should_step:
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
        predictions = torch.sigmoid(logits.detach()) >= 0.5
        targets_binary = targets >= 0.5
        intersection = (predictions & targets_binary).flatten(1).sum(dim=1).float()
        denominator = (
            predictions.flatten(1).sum(dim=1).float() + targets_binary.flatten(1).sum(dim=1).float()
        )
        dice = torch.where(
            denominator > 0, 2 * intersection / denominator, torch.ones_like(denominator)
        )
        batch_size = images.shape[0]
        total_loss += float(loss.detach()) * batch_size
        total_dice += float(dice.sum())
        total_images += batch_size
    return total_loss / total_images, total_dice / total_images


def train_model(
    model: nn.Module,
    train_loader: DataLoader[dict[str, Any]],
    dev_loader: DataLoader[dict[str, Any]],
    config: dict[str, Any],
    run_dir: str | Path,
    *,
    manifest_hash: str,
    device: str = "cpu",
    resume: bool = False,
    stop_after_epoch: int | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    training = config["training"]
    model_name = str(config["model"]["name"])
    resolved_hash = config_hash(config)
    seed = int(config["project"]["seed"])
    seed_everything(seed, bool(config["runtime"].get("deterministic_warn_only", True)))
    torch_device = resolve_device(device)
    model.to(torch_device)
    criterion = build_loss(str(training["loss"]))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    max_epochs = int(training["max_epochs"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, max_epochs))
    use_amp = bool(training["amp"]) and torch_device.type == "cuda"
    scaler = torch.amp.GradScaler(torch_device.type, enabled=use_amp)
    start_epoch = 0
    best_dice = -1.0
    stale_epochs = 0
    history: list[dict[str, Any]] = []
    resume_verified = False
    resumed_from_epoch: int | None = None
    interrupted_for_resume_test = False
    last_weights = run_dir / "last_model.safetensors"
    state_path = run_dir / "trainer_state.pt"
    if resume and state_path.exists() and last_weights.exists():
        payload = load_trainer_state(
            state_path,
            expected_config_hash=resolved_hash,
            expected_manifest_hash=manifest_hash,
            expected_model_name=model_name,
        )
        load_model_safetensors(model, last_weights)
        optimizer.load_state_dict(payload["optimizer"])
        scheduler.load_state_dict(payload["scheduler"])
        scaler.load_state_dict(payload["scaler"])
        restore_rng_state(payload["rng_state"])
        start_epoch = int(payload["epoch"]) + 1
        best_dice = float(payload["best_dice"])
        stale_epochs = int(payload["stale_epochs"])
        history = list(payload["history"])
        resume_verified = True
        resumed_from_epoch = int(payload["epoch"])

    writer = SummaryWriter(run_dir / "tensorboard")
    for epoch in range(start_epoch, max_epochs):
        train_loss, train_dice = _run_epoch(
            model,
            train_loader,
            criterion,
            torch_device,
            optimizer=optimizer,
            scaler=scaler,
            accumulation=int(training["gradient_accumulation"]),
            amp=use_amp,
        )
        dev_loss, dev_dice = _run_epoch(
            model,
            dev_loader,
            criterion,
            torch_device,
            optimizer=None,
            scaler=scaler,
            accumulation=1,
            amp=use_amp,
        )
        scheduler.step()
        row = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_dice": train_dice,
            "dev_loss": dev_loss,
            "dev_dice": dev_dice,
            "learning_rate": optimizer.param_groups[0]["lr"],
        }
        if not all(math.isfinite(float(value)) for value in row.values()):
            raise RuntimeError(f"Non-finite training metric at epoch {epoch}: {row}")
        history.append(row)
        for name, value in row.items():
            if name != "epoch":
                writer.add_scalar(name, value, epoch)
        improved = dev_dice > best_dice + float(training["early_stopping_min_delta"])
        if improved:
            best_dice = dev_dice
            stale_epochs = 0
            save_model_safetensors(model, run_dir / "best_model.safetensors")
        else:
            stale_epochs += 1
        save_model_safetensors(model, last_weights)
        save_trainer_state(
            {
                "epoch": epoch,
                "config_hash": resolved_hash,
                "manifest_hash": manifest_hash,
                "model_name": model_name,
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "scaler": scaler.state_dict(),
                "rng_state": capture_rng_state(),
                "best_dice": best_dice,
                "stale_epochs": stale_epochs,
                "history": history,
            },
            state_path,
        )
        _write_history(history, run_dir / "history.csv")
        write_json_atomic(
            {
                "status": "running",
                "last_completed_epoch": epoch,
                "best_dev_dice": best_dice,
                "config_hash": resolved_hash,
                "manifest_hash": manifest_hash,
            },
            run_dir / "results.partial.json",
        )
        writer.flush()
        if (
            stop_after_epoch is not None
            and len(history) >= stop_after_epoch
            and epoch + 1 < max_epochs
        ):
            interrupted_for_resume_test = True
            write_json_atomic(
                {
                    "status": "interrupted_for_resume_test",
                    "last_completed_epoch": epoch,
                    "best_dev_dice": best_dice,
                    "config_hash": resolved_hash,
                    "manifest_hash": manifest_hash,
                },
                run_dir / "results.partial.json",
            )
            break
        if stale_epochs >= int(training["early_stopping_patience"]):
            break
    writer.close()
    if interrupted_for_resume_test:
        return {
            "status": "interrupted_for_resume_test",
            "best_dev_dice": best_dice,
            "epochs_completed": len(history),
            "history": history,
            "config_hash": resolved_hash,
            "manifest_hash": manifest_hash,
            "device": str(torch_device),
            "amp_enabled": use_amp,
            "resume_verified": resume_verified,
            "resumed_from_epoch": resumed_from_epoch,
            "best_checkpoint_sha256": file_sha256(run_dir / "best_model.safetensors"),
            "last_checkpoint_sha256": file_sha256(last_weights),
        }
    result = {
        "status": "completed",
        "best_dev_dice": best_dice,
        "epochs_completed": len(history),
        "history": history,
        "config_hash": resolved_hash,
        "manifest_hash": manifest_hash,
        "device": str(torch_device),
        "amp_enabled": use_amp,
        "resume_verified": resume_verified,
        "resumed_from_epoch": resumed_from_epoch,
        "best_checkpoint_sha256": file_sha256(run_dir / "best_model.safetensors"),
        "last_checkpoint_sha256": file_sha256(last_weights),
    }
    write_json_atomic(result, run_dir / "results.json")
    return result
