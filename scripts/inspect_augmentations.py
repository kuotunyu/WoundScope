"""Write a local, gitignored grid for conservative augmentation inspection."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from woundscope.augmentations import save_augmentation_grid
from woundscope.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/base.yaml"))
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("reports/generated/augmentations.png"))
    parser.add_argument("--image-size", type=int, default=None)
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    config = load_config(args.config)
    image_size = args.image_size or int(config["data"]["image_size"])
    with Image.open(args.image) as source:
        image = np.asarray(source.convert("RGB"))
    with Image.open(args.mask) as source:
        mask = (np.asarray(source.convert("L")) >= 128).astype(np.uint8)
    if image.shape[0] != image_size or image.shape[1] != image_size:
        image = np.asarray(Image.fromarray(image).resize((image_size, image_size)))
        mask = np.asarray(
            Image.fromarray(mask).resize((image_size, image_size), Image.Resampling.NEAREST)
        )
    save_augmentation_grid(image, mask, args.output, samples=args.samples)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
