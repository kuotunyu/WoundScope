"""Immutable public evidence locks for the Pages projection."""

from __future__ import annotations

from typing import Final

BASE_PATH: Final = "/WoundScope/"
SITE_BUILD_MODE: Final = "static-github-pages-review"
CLAIM_BOUNDARY_VERSION: Final = "2026-08-31"
NETWORK_CONTRACT_VERSION: Final = "2026-08-31"

TAG_NAME: Final = "v0.2.2"
TAG_REF: Final = "refs/tags/v0.2.2"
TAG_OBJECT: Final = "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4"
PEELED_COMMIT: Final = "1b3df3b516cc4d366dc9da3cb01e8d0a319be613"
EXPECTED_TAGGER: Final = "kuotunyu <61350295+kuotunyu@users.noreply.github.com>"

README_PATH: Final = "README.md"
DATA_CARD_PATH: Final = "DATA_CARD.md"
MODEL_CARD_PATH: Final = "MODEL_CARD.md"
SVG_PATH: Final = "reports/public/model_comparison.svg"
LICENSE_PATH: Final = "LICENSE"

README_BLOB: Final = "f5b8dd4681738aa372072cac9c827478d13c1f68"
DATA_CARD_BLOB: Final = "2b7fe52ac9784c9c2682300d2bd56bb72b20d19c"
MODEL_CARD_BLOB: Final = "c93a99579ad1b4fb1d03b0a6e15ba8300287ca9c"
SVG_BLOB: Final = "28d91ba5f6fb61d1114106e7519007d6aeb5d6b8"
LICENSE_BLOB: Final = "6d7d4eed049964731c06b000d257a1bdb2fd6028"
EXPECTED_LICENSE_LENGTH: Final = 11577
EXPECTED_LICENSE_SHA256: Final = (
    "7203278db33515a51443fb4969f84deabc6081086c55a59cc94ee2a384c83f7d"
)

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

EXPECTED_CSP: Final = (
    "default-src 'none'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "font-src 'none'; "
    "script-src 'none'; "
    "connect-src 'none'; "
    "media-src 'none'; "
    "object-src 'none'; "
    "frame-src 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "manifest-src 'none'"
)

AUTHORED_SITE_FILES: Final = (
    "index.template.html",
    "404.template.html",
    "site.css",
    "links.allowlist.json",
    "THIRD_PARTY_NOTICES.txt",
)

PUBLISH_FILE_BUDGETS: Final = {
    ".nojekyll": 0,
    "index.html": 65536,
    "404.html": 8192,
    "LICENSE.txt": 11577,
    "THIRD_PARTY_NOTICES.txt": 16384,
    "sbom.spdx.json": 65536,
    "pages-manifest.json": 32768,
}
MAX_CSS_BYTES: Final = 32768
MAX_TOTAL_PUBLISH_BYTES: Final = 237568

FORBIDDEN_METRIC_LITERALS: Final = (
    "0.8508",
    "0.8270",
    "0.7772",
    "0.7437",
)

EXTERNAL_LINK_ALLOWLIST: Final = (
    "https://github.com/kuotunyu/WoundScope",
    "https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.2",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/README.md",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/DATA_CARD.md",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/MODEL_CARD.md",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/CITATION.cff",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/LICENSE",
    "https://doi.org/10.1038/s41598-020-78799-w",
    "https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge",
)

REVIEW_REPORT_FILES: Final = (
    "toolchain.json",
    "network.json",
    "axe.json",
    "keyboard.json",
    "contrast.json",
    "zoom.json",
    "browser-summary.json",
)
REVIEW_SCREENSHOT_DIRECTORY: Final = "screenshots"
REVIEW_SCREENSHOT_SUFFIX: Final = ".png"
EXPECTED_BROWSER_REVISIONS: Final = {
    "chromium": "1234",
    "firefox": "1538",
    "webkit": "2336",
}
MANUAL_BROWSER_ZOOM_FIELD: Final = "manual_browser_zoom_200_percent"
