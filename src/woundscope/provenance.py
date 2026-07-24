"""Run provenance capture without leaking environment secrets."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch

from woundscope.checkpointing import file_sha256
from woundscope.config import config_hash


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def _git_dirty() -> bool | None:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return bool(completed.stdout.strip()) if completed.returncode == 0 else None


def build_provenance(
    config: dict[str, Any],
    manifest_path: str | Path,
    *,
    seed: int,
    device: str,
) -> dict[str, Any]:
    packages = {}
    for name in (
        "torch",
        "torchvision",
        "albumentations",
        "segmentation-models-pytorch",
        "transformers",
        "onnxruntime",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not-installed"
    return {
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "data_revision": config["data"]["source_revision"],
        "manifest_sha256": file_sha256(manifest_path),
        "config_sha256": config_hash(config),
        "seed": seed,
        "device": device,
        "python": sys.version,
        "platform": platform.platform(),
        "packages": packages,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "cudnn_version": torch.backends.cudnn.version() if torch.cuda.is_available() else None,
    }


def write_json_atomic(payload: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
