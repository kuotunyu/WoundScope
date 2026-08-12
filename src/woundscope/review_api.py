"""Privacy-safe FastAPI boundary for the WoundScope review workbench."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Annotated, Protocol

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from woundscope import __version__
from woundscope.inference import PredictionResult, create_overlay
from woundscope.model_runtime import ModelStatus, inspect_model_status, load_predictor

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_IMAGE_DIMENSION = 8192
ALLOWED_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
ALLOWED_IMAGE_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})


class ReviewRuntime(Protocol):
    def status(self) -> ModelStatus: ...

    def predict(self, image: Image.Image) -> PredictionResult: ...


class _DefaultReviewRuntime:
    def status(self) -> ModelStatus:
        return inspect_model_status()

    def predict(self, image: Image.Image) -> PredictionResult:
        return load_predictor().predict(image)


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def _decode_upload(upload: UploadFile) -> Image.Image:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise _api_error(422, "INVALID_IMAGE", "僅接受 PNG、JPEG 或 WebP 影像。")
    payload = await upload.read(MAX_UPLOAD_BYTES + 1)
    await upload.close()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise _api_error(413, "IMAGE_TOO_LARGE", "影像大小不可超過 12 MiB。")
    try:
        with Image.open(io.BytesIO(payload)) as source:
            if source.format not in ALLOWED_IMAGE_FORMATS:
                raise _api_error(422, "INVALID_IMAGE", "影像格式無法辨識。")
            width, height = source.size
            if width < 1 or height < 1 or max(width, height) > MAX_IMAGE_DIMENSION:
                raise _api_error(422, "INVALID_IMAGE", "影像尺寸超出安全範圍。")
            source.load()
            return source.convert("RGB")
    except HTTPException:
        raise
    except (OSError, UnidentifiedImageError, ValueError):
        raise _api_error(422, "INVALID_IMAGE", "影像內容無法解碼。") from None


def _png_data_url(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _prediction_response(
    image: Image.Image,
    result: PredictionResult,
    status: ModelStatus,
) -> dict[str, object]:
    overlay = create_overlay(image, result.mask, alpha=0.45)
    mask = Image.fromarray(np.asarray(result.mask, dtype=np.uint8) * 255, mode="L")
    return {
        "overlay_data_url": _png_data_url(overlay),
        "mask_data_url": _png_data_url(mask),
        "wound_pixel_ratio": result.wound_pixel_ratio,
        "confidence_score": result.confidence.score,
        "confidence_label": "模型分割信心，非臨床信心",
        "inference_ms": result.inference_seconds * 1000,
        "low_confidence": result.confidence.low_confidence,
        "review_reasons": list(result.confidence.reasons),
        "provider": status.provider,
    }


def create_app(
    runtime: ReviewRuntime | None = None,
    frontend_dir: Path | None = None,
) -> FastAPI:
    del frontend_dir  # Static hosting is introduced in the dedicated integration task.
    selected_runtime = runtime or _DefaultReviewRuntime()
    app = FastAPI(
        title="WoundScope Review API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "application": "WoundScope", "version": __version__}

    @app.get("/api/model-status")
    def model_status() -> dict[str, object]:
        status = selected_runtime.status()
        return {
            "mode": status.mode.value,
            "model_available": status.model_available,
            "calibration_available": status.calibration_available,
            "model_label": status.model_label,
            "model_sha256_prefix": status.model_sha256_prefix,
            "provider": status.provider,
            "message": status.message,
        }

    @app.post("/api/predict")
    async def predict(image: Annotated[UploadFile, File()]) -> dict[str, object]:
        status = selected_runtime.status()
        if not status.model_available:
            raise _api_error(
                503,
                "MODEL_NOT_AVAILABLE",
                "本機模型尚未就緒，目前僅提供研究展示模式。",
            )
        decoded = await _decode_upload(image)
        try:
            result = selected_runtime.predict(decoded)
            return _prediction_response(decoded, result, status)
        except Exception:
            raise _api_error(
                500,
                "INFERENCE_FAILED",
                "分割推論失敗，未保留上傳內容。",
            ) from None

    return app
