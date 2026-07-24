"""Atomic model persistence and resume metadata verification."""

from __future__ import annotations

import hashlib
import os
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from safetensors.torch import load_file, save_file
from torch import nn


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cpu_state_dict(model: nn.Module) -> dict[str, torch.Tensor]:
    return {name: tensor.detach().cpu().contiguous() for name, tensor in model.state_dict().items()}


def save_model_safetensors(model: nn.Module, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    save_file(_cpu_state_dict(model), temporary)
    os.replace(temporary, path)
    return file_sha256(path)


def load_model_safetensors(model: nn.Module, path: str | Path, strict: bool = True) -> None:
    state = load_file(Path(path), device="cpu")
    model.load_state_dict(state, strict=strict)


def capture_rng_state() -> dict[str, Any]:
    state: dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["cuda"] = torch.cuda.get_rng_state_all()
    return state


def restore_rng_state(state: dict[str, Any]) -> None:
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if "cuda" in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(state["cuda"])


def save_trainer_state(payload: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def load_trainer_state(
    path: str | Path,
    *,
    expected_config_hash: str,
    expected_manifest_hash: str,
    expected_model_name: str,
) -> dict[str, Any]:
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    expected = {
        "config_hash": expected_config_hash,
        "manifest_hash": expected_manifest_hash,
        "model_name": expected_model_name,
    }
    mismatches = [
        f"{key}: expected {value!r}, found {payload.get(key)!r}"
        for key, value in expected.items()
        if payload.get(key) != value
    ]
    if mismatches:
        raise ValueError("Incompatible trainer state: " + "; ".join(mismatches))
    return payload
