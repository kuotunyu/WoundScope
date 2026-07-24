from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset

from woundscope.models import TinyUNet
from woundscope.training import train_model


class _SyntheticSegmentationDataset(Dataset[dict[str, Any]]):
    def __len__(self) -> int:
        return 4

    def __getitem__(self, index: int) -> dict[str, Any]:
        generator = torch.Generator().manual_seed(index)
        image = torch.rand((3, 32, 32), generator=generator)
        mask = torch.zeros((1, 32, 32))
        mask[:, 8:24, 8:24] = 1
        return {"image": image, "mask": mask, "sample_id": str(index)}


def _config() -> dict[str, Any]:
    return {
        "project": {"seed": 42},
        "model": {"name": "tiny_unet", "family": "tiny_unet"},
        "training": {
            "loss": "bce_dice",
            "learning_rate": 0.001,
            "weight_decay": 0.0,
            "max_epochs": 1,
            "gradient_accumulation": 1,
            "amp": False,
            "early_stopping_min_delta": 0.0001,
            "early_stopping_patience": 2,
        },
        "runtime": {"deterministic_warn_only": True},
    }


def test_one_epoch_vertical_slice_persists_and_resumes(tmp_path: Path) -> None:
    torch.set_num_threads(1)
    loader = DataLoader(_SyntheticSegmentationDataset(), batch_size=2)
    run_dir = tmp_path / "run"
    model = TinyUNet(base_channels=2)

    result = train_model(
        model,
        loader,
        loader,
        _config(),
        run_dir,
        manifest_hash="synthetic-manifest",
        device="cpu",
    )

    assert result["status"] == "completed"
    assert result["epochs_completed"] == 1
    assert len(result["best_checkpoint_sha256"]) == 64
    assert len(result["last_checkpoint_sha256"]) == 64
    for name in (
        "best_model.safetensors",
        "last_model.safetensors",
        "trainer_state.pt",
        "history.csv",
        "results.json",
        "results.partial.json",
    ):
        assert (run_dir / name).is_file()

    resumed = train_model(
        TinyUNet(base_channels=2),
        loader,
        loader,
        _config(),
        run_dir,
        manifest_hash="synthetic-manifest",
        device="cpu",
        resume=True,
    )
    assert resumed["epochs_completed"] == 1
