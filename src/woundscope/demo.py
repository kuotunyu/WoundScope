"""Gradio-facing pure function kept separate from server startup."""

from __future__ import annotations

from PIL import Image

from woundscope.inference import Predictor, create_overlay


def process_for_demo(
    image: Image.Image | None, predictor: Predictor
) -> tuple[Image.Image, Image.Image, str, str, str, str]:
    if image is None:
        raise ValueError("請先上傳影像")
    original = image.convert("RGB")
    result = predictor.predict(original)
    overlay = create_overlay(original, result.mask)
    confidence = f"{result.confidence.score * 100:.1f}%（模型分割信心，非臨床信心）"
    ratio = f"{result.wound_pixel_ratio * 100:.2f}%"
    timing = f"{result.inference_seconds * 1000:.1f} ms"
    if result.confidence.low_confidence:
        warning = "需人工複核：" + ", ".join(result.confidence.reasons)
    else:
        warning = "未觸發低信心規則；仍應由合格人員複核。"
    return original, overlay, ratio, confidence, timing, warning
