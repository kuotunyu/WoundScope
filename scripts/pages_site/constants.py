"""Immutable public evidence locks for the Pages projection."""

from __future__ import annotations

from typing import Final

TAG_NAME: Final = "v0.2.2"
TAG_REF: Final = "refs/tags/v0.2.2"
TAG_OBJECT: Final = "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4"
PEELED_COMMIT: Final = "1b3df3b516cc4d366dc9da3cb01e8d0a319be613"
EXPECTED_TAGGER: Final = "kuotunyu <61350295+kuotunyu@users.noreply.github.com>"

README_PATH: Final = "README.md"
DATA_CARD_PATH: Final = "DATA_CARD.md"
MODEL_CARD_PATH: Final = "MODEL_CARD.md"
SVG_PATH: Final = "reports/public/model_comparison.svg"

README_BLOB: Final = "f5b8dd4681738aa372072cac9c827478d13c1f68"
DATA_CARD_BLOB: Final = "2b7fe52ac9784c9c2682300d2bd56bb72b20d19c"
MODEL_CARD_BLOB: Final = "c93a99579ad1b4fb1d03b0a6e15ba8300287ca9c"
SVG_BLOB: Final = "28d91ba5f6fb61d1114106e7519007d6aeb5d6b8"

RESULTS_TABLE_START: Final = b"<!-- RESULTS_TABLE_START -->"
RESULTS_TABLE_END: Final = b"<!-- RESULTS_TABLE_END -->"

EXPECTED_COLUMNS: Final = (
    "Model",
    "Loss",
    "Seeds",
    "Dice mean±SD (95% CI)",
    "IoU",
    "Precision",
    "Recall",
    "Specificity",
)
EXPECTED_MODEL_IDS: Final = ("unet_efficientnet_b0", "segformer_b0")
EXPECTED_LOSS: Final = "bce_dice"
EXPECTED_SEEDS: Final = (42, 43, 44)
EXPECTED_MODEL_DISPLAY_NAMES: Final = (
    "EfficientNet-B0 U-Net",
    "SegFormer-B0",
)

EXPECTED_PUBLIC_SVG_LENGTH: Final = 3009
EXPECTED_PUBLIC_SVG_SHA256: Final = (
    "1eafa7c35b06928b6cfc2910326f9c0adaf88098ab3a734ba43e16914fd7814d"
)
EXPECTED_PUBLIC_SVG_FILENAME: Final = "model-comparison-1eafa7c35b06928b.svg"
EXPECTED_PUBLIC_SVG_TITLE: Final = "WoundScope locked official-validation aggregate comparison"
EXPECTED_PUBLIC_SVG_DESC: Final = (
    "EfficientNet-B0 U-Net and SegFormer-B0 aggregate Dice and IoU across three "
    "training seeds on locked official validation."
)
EXPECTED_PUBLIC_SVG_HEADLINE: Final = "Locked official-validation aggregate"
EXPECTED_PUBLIC_SVG_SUBHEAD: Final = "EfficientNet-B0 U-Net vs SegFormer-B0 · BCE+Dice · n=3 seeds"
EXPECTED_PUBLIC_SVG_FOOTNOTE: Final = (
    "locked official validation · n=3 seeds · not official-test or clinical performance"
)
