"""Manifest-driven FUSeg dataset with portable relative paths."""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from woundscope.augmentations import build_transform


def read_manifest(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FUSegDataset(Dataset[dict[str, Any]]):
    def __init__(
        self,
        challenge_dir: str | Path,
        manifest_path: str | Path,
        selector: str,
        *,
        transform: Callable[..., dict[str, Any]] | None = None,
        require_mask: bool = True,
        limit: int | None = None,
        excluded_keys: set[str] | None = None,
    ) -> None:
        self.challenge_dir = Path(challenge_dir)
        rows = read_manifest(manifest_path)
        excluded_keys = excluded_keys or set()
        self.rows = [
            row
            for row in rows
            if row["internal_split"] == selector or row["split"] == selector
            if f"{row['split']}/{row['sample_id']}" not in excluded_keys
        ]
        if limit is not None:
            self.rows = self.rows[:limit]
        if not self.rows:
            raise ValueError(f"No manifest rows matched selector: {selector}")
        if require_mask and any(row["has_mask"].casefold() != "true" for row in self.rows):
            raise ValueError(f"Selector contains samples without masks: {selector}")
        self.transform = transform
        self.require_mask = require_mask

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        row = self.rows[index]
        image_path = self.challenge_dir / row["image_relpath"]
        with Image.open(image_path) as source:
            image = np.asarray(source.convert("RGB"), dtype=np.uint8)
        original_size = (image.shape[1], image.shape[0])
        if row["mask_relpath"]:
            with Image.open(self.challenge_dir / row["mask_relpath"]) as source:
                mask = (np.asarray(source.convert("L")) >= 128).astype(np.float32)
        else:
            mask = np.zeros(image.shape[:2], dtype=np.float32)
        if self.transform is not None:
            transformed = self.transform(image=image, mask=mask)
            image_tensor = transformed["image"].float()
            mask_tensor = transformed["mask"].float()
        else:
            image_tensor = torch.from_numpy(image.transpose(2, 0, 1)).float() / 255
            mask_tensor = torch.from_numpy(mask).float()
        if mask_tensor.ndim == 2:
            mask_tensor = mask_tensor.unsqueeze(0)
        return {
            "image": image_tensor,
            "mask": mask_tensor,
            "sample_id": row["sample_id"],
            "official_split": row["split"],
            "internal_split": row["internal_split"],
            "original_size": original_size,
        }


def build_dataloader(
    challenge_dir: str | Path,
    manifest_path: str | Path,
    selector: str,
    *,
    image_size: int,
    batch_size: int,
    train: bool,
    num_workers: int = 0,
    limit: int | None = None,
    require_mask: bool = True,
    excluded_keys: set[str] | None = None,
) -> DataLoader[dict[str, Any]]:
    dataset = FUSegDataset(
        challenge_dir,
        manifest_path,
        selector,
        transform=build_transform(image_size=image_size, train=train),
        require_mask=require_mask,
        limit=limit,
        excluded_keys=excluded_keys,
    )
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=train,
        num_workers=num_workers,
        pin_memory=False,
        drop_last=False,
    )
