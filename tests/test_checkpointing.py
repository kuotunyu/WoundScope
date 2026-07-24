from __future__ import annotations

from pathlib import Path

import pytest
import torch

from woundscope.checkpointing import (
    capture_rng_state,
    load_model_safetensors,
    load_trainer_state,
    save_model_safetensors,
    save_trainer_state,
)
from woundscope.models import TinyUNet


def test_safetensors_model_round_trip(tmp_path: Path) -> None:
    source = TinyUNet(base_channels=2)
    target = TinyUNet(base_channels=2)
    path = tmp_path / "model.safetensors"

    digest = save_model_safetensors(source, path)
    load_model_safetensors(target, path)

    assert len(digest) == 64
    for source_tensor, target_tensor in zip(
        source.state_dict().values(), target.state_dict().values(), strict=True
    ):
        assert torch.equal(source_tensor, target_tensor)


def test_trainer_state_compatibility_gate(tmp_path: Path) -> None:
    path = tmp_path / "trainer_state.pt"
    payload = {
        "epoch": 2,
        "config_hash": "config",
        "manifest_hash": "manifest",
        "model_name": "tiny",
        "rng_state": capture_rng_state(),
    }
    save_trainer_state(payload, path)

    loaded = load_trainer_state(
        path,
        expected_config_hash="config",
        expected_manifest_hash="manifest",
        expected_model_name="tiny",
    )
    assert loaded["epoch"] == 2

    with pytest.raises(ValueError, match="Incompatible trainer state"):
        load_trainer_state(
            path,
            expected_config_hash="different",
            expected_manifest_hash="manifest",
            expected_model_name="tiny",
        )
