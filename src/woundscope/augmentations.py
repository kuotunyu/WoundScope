"""Conservative, mask-aware augmentation and visual inspection."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import albumentations as A
import cv2
import matplotlib.pyplot as plt
import numpy as np
from albumentations.pytorch import ToTensorV2


class MaskPreservingRandomCrop:
    """Apply a mild crop only when at least `min_foreground_retention` remains."""

    def __init__(
        self,
        probability: float = 0.5,
        min_scale: float = 0.9,
        min_foreground_retention: float = 0.9,
        attempts: int = 8,
    ) -> None:
        self.probability = probability
        self.min_scale = min_scale
        self.min_foreground_retention = min_foreground_retention
        self.attempts = attempts

    def __call__(self, image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if random.random() >= self.probability:
            return image, mask
        height, width = mask.shape[:2]
        foreground = int(np.count_nonzero(mask))
        for _ in range(self.attempts):
            scale = random.uniform(self.min_scale, 1.0)
            crop_height = max(1, round(height * scale))
            crop_width = max(1, round(width * scale))
            top = random.randint(0, height - crop_height)
            left = random.randint(0, width - crop_width)
            crop_mask = mask[top : top + crop_height, left : left + crop_width]
            retained = 1.0 if foreground == 0 else np.count_nonzero(crop_mask) / foreground
            if retained >= self.min_foreground_retention:
                return (
                    image[top : top + crop_height, left : left + crop_width],
                    crop_mask,
                )
        return image, mask


class SegmentationTransform:
    def __init__(self, image_size: int = 512, train: bool = False) -> None:
        self.crop = MaskPreservingRandomCrop() if train else None
        transforms: list[A.BasicTransform] = [
            A.LongestMaxSize(max_size=image_size),
            A.PadIfNeeded(
                min_height=image_size,
                min_width=image_size,
                border_mode=cv2.BORDER_CONSTANT,
                fill=0,
                fill_mask=0,
            ),
        ]
        if train:
            transforms.extend(
                [
                    A.HorizontalFlip(p=0.5),
                    A.Affine(
                        scale=(0.95, 1.05),
                        translate_percent=(-0.05, 0.05),
                        rotate=(-10, 10),
                        border_mode=cv2.BORDER_CONSTANT,
                        fill=0,
                        fill_mask=0,
                        p=0.6,
                    ),
                    A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.15, p=0.4),
                    A.HueSaturationValue(
                        hue_shift_limit=5,
                        sat_shift_limit=10,
                        val_shift_limit=8,
                        p=0.3,
                    ),
                ]
            )
        transforms.extend(
            [
                A.Normalize(
                    mean=(0.485, 0.456, 0.406),
                    std=(0.229, 0.224, 0.225),
                    max_pixel_value=255.0,
                ),
                ToTensorV2(),
            ]
        )
        self.compose = A.Compose(transforms)

    def __call__(self, image: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
        if self.crop is not None:
            image, mask = self.crop(image, mask)
        return self.compose(image=image, mask=mask)


def build_transform(image_size: int = 512, train: bool = False) -> SegmentationTransform:
    return SegmentationTransform(image_size=image_size, train=train)


def save_augmentation_grid(
    image: np.ndarray,
    mask: np.ndarray,
    output_path: str | Path,
    *,
    samples: int = 6,
    seed: int = 42,
) -> Path:
    """Save a deterministic image/mask overlay grid for human semantic review."""

    random.seed(seed)
    np.random.seed(seed)
    transform = build_transform(image_size=image.shape[0], train=True)
    figure, axes = plt.subplots(2, samples, figsize=(3 * samples, 6))
    for index in range(samples):
        transformed = transform(image=image, mask=mask)
        tensor = transformed["image"].numpy().transpose(1, 2, 0)
        tensor = tensor * np.array((0.229, 0.224, 0.225)) + np.array((0.485, 0.456, 0.406))
        restored = np.clip(tensor * 255, 0, 255).astype(np.uint8)
        transformed_mask = transformed["mask"].numpy()
        axes[0, index].imshow(restored)
        axes[0, index].axis("off")
        axes[1, index].imshow(restored)
        axes[1, index].imshow(transformed_mask, alpha=0.4, cmap="Reds", vmin=0, vmax=1)
        axes[1, index].axis("off")
    figure.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=140)
    plt.close(figure)
    return output_path
