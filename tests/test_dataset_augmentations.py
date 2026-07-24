from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
from PIL import Image

from woundscope.augmentations import (
    MaskPreservingRandomCrop,
    build_transform,
    save_augmentation_grid,
)
from woundscope.dataset import FUSegDataset


def test_mask_preserving_crop_retains_foreground() -> None:
    random.seed(42)
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    mask = np.zeros((64, 64), dtype=np.uint8)
    mask[20:44, 20:44] = 1
    crop = MaskPreservingRandomCrop(
        probability=1.0, min_scale=0.6, min_foreground_retention=0.9, attempts=20
    )

    _cropped_image, cropped_mask = crop(image, mask)

    assert np.count_nonzero(cropped_mask) / np.count_nonzero(mask) >= 0.9


def test_transform_produces_expected_tensor_shapes() -> None:
    image = np.zeros((40, 64, 3), dtype=np.uint8)
    mask = np.zeros((40, 64), dtype=np.float32)
    mask[10:20, 20:30] = 1

    transformed = build_transform(image_size=64, train=False)(image=image, mask=mask)

    assert tuple(transformed["image"].shape) == (3, 64, 64)
    assert tuple(transformed["mask"].shape) == (64, 64)


def test_manifest_dataset_restores_binary_mask(tmp_path: Path) -> None:
    challenge = tmp_path / "challenge"
    image_path = challenge / "train" / "images" / "one.png"
    mask_path = challenge / "train" / "labels" / "one.png"
    image_path.parent.mkdir(parents=True)
    mask_path.parent.mkdir(parents=True)
    Image.fromarray(np.full((32, 48, 3), 120, dtype=np.uint8), mode="RGB").save(image_path)
    mask = np.zeros((32, 48), dtype=np.uint8)
    mask[8:24, 12:36] = 255
    Image.fromarray(mask, mode="L").save(mask_path)
    manifest = tmp_path / "manifest.csv"
    fields = [
        "split",
        "sample_id",
        "image_relpath",
        "mask_relpath",
        "has_mask",
        "internal_split",
    ]
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "split": "train",
                "sample_id": "one",
                "image_relpath": "train/images/one.png",
                "mask_relpath": "train/labels/one.png",
                "has_mask": "True",
                "internal_split": "train",
            }
        )

    dataset = FUSegDataset(
        challenge,
        manifest,
        "train",
        transform=build_transform(image_size=64, train=False),
    )
    sample = dataset[0]

    assert tuple(sample["image"].shape) == (3, 64, 64)
    assert tuple(sample["mask"].shape) == (1, 64, 64)
    assert set(sample["mask"].unique().tolist()) <= {0.0, 1.0}
    assert sample["original_size"] == (48, 32)


def test_augmentation_inspection_grid_is_persisted(tmp_path: Path) -> None:
    image = np.full((32, 32, 3), 120, dtype=np.uint8)
    mask = np.zeros((32, 32), dtype=np.uint8)
    mask[8:24, 8:24] = 1

    output = save_augmentation_grid(image, mask, tmp_path / "grid.png", samples=3)

    assert output.is_file()
    with Image.open(output) as rendered:
        assert rendered.width > rendered.height
