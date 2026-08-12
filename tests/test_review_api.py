from __future__ import annotations

import asyncio
import io
from dataclasses import replace

import httpx
import numpy as np
import pytest
from PIL import Image

from woundscope.inference import PredictionResult
from woundscope.model_runtime import ModelStatus, RuntimeMode
from woundscope.review_api import create_app
from woundscope.uncertainty import ConfidenceResult


def _png_bytes(*, width: int = 32, height: int = 24) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (width, height), color=(128, 134, 129)).save(stream, format="PNG")
    return stream.getvalue()


def _request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://woundscope.test",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


READY_STATUS = ModelStatus(
    mode=RuntimeMode.LOCAL_REVIEW,
    model_available=True,
    calibration_available=True,
    model_label="Synthetic ONNX",
    provider="CPUExecutionProvider",
    message="本機模型已就緒。",
    model_sha256_prefix="abc123def456",
)

SHOWCASE_STATUS = ModelStatus(
    mode=RuntimeMode.SHOWCASE,
    model_available=False,
    calibration_available=False,
    model_label="EfficientNet-B0 U-Net / ONNX",
    provider="unavailable",
    message="目前為研究展示模式。",
)


class SyntheticRuntime:
    def __init__(self, status: ModelStatus = READY_STATUS) -> None:
        self._status = status
        self.predict_calls = 0

    def status(self) -> ModelStatus:
        return self._status

    def predict(self, image: Image.Image) -> PredictionResult:
        self.predict_calls += 1
        mask = np.zeros((image.height, image.width), dtype=bool)
        top = image.height // 4
        left = image.width // 4
        mask[top : image.height - top, left : image.width - left] = True
        return PredictionResult(
            mask=mask,
            probability=mask.astype(np.float32),
            wound_pixel_ratio=float(mask.mean()),
            confidence=ConfidenceResult(
                score=0.82,
                entropy_certainty=0.8,
                tta_agreement=0.84,
                low_confidence=True,
                reasons=("confidence_below_dev_cutoff",),
            ),
            inference_seconds=0.012,
        )


def test_health_does_not_inspect_or_load_model() -> None:
    class HealthOnlyRuntime:
        def status(self) -> ModelStatus:
            raise AssertionError("health must not inspect model status")

        def predict(self, image: Image.Image) -> PredictionResult:
            raise AssertionError("health must not run inference")

    response = _request(create_app(runtime=HealthOnlyRuntime()), "GET", "/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "WoundScope", "version": "0.2.1"}


def test_model_status_exposes_only_safe_readiness_fields() -> None:
    response = _request(create_app(runtime=SyntheticRuntime()), "GET", "/api/model-status")

    assert response.status_code == 200
    assert response.json() == {
        "mode": "local_review",
        "model_available": True,
        "calibration_available": True,
        "model_label": "Synthetic ONNX",
        "model_sha256_prefix": "abc123def456",
        "provider": "CPUExecutionProvider",
        "message": "本機模型已就緒。",
    }


def test_predict_returns_in_memory_assets_and_nonclinical_metrics() -> None:
    runtime = SyntheticRuntime()
    response = _request(
        create_app(runtime=runtime),
        "POST",
        "/api/predict",
        files={"image": ("synthetic.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overlay_data_url"].startswith("data:image/png;base64,")
    assert body["mask_data_url"].startswith("data:image/png;base64,")
    assert body["wound_pixel_ratio"] == pytest.approx(0.25)
    assert body["confidence_score"] == pytest.approx(0.82)
    assert body["confidence_label"] == "模型分割信心，非臨床信心"
    assert body["inference_ms"] == pytest.approx(12.0)
    assert body["low_confidence"] is True
    assert body["review_reasons"] == ["confidence_below_dev_cutoff"]
    assert body["provider"] == "CPUExecutionProvider"
    assert runtime.predict_calls == 1


def test_showcase_mode_refuses_prediction() -> None:
    runtime = SyntheticRuntime(SHOWCASE_STATUS)
    response = _request(
        create_app(runtime=runtime),
        "POST",
        "/api/predict",
        files={"image": ("synthetic.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "MODEL_NOT_AVAILABLE",
            "message": "本機模型尚未就緒，目前僅提供研究展示模式。",
        }
    }
    assert runtime.predict_calls == 0


@pytest.mark.parametrize(
    ("payload", "content_type"),
    [
        (b"not-an-image", "image/png"),
        (_png_bytes(), "application/octet-stream"),
    ],
)
def test_invalid_image_is_rejected(payload: bytes, content_type: str) -> None:
    response = _request(
        create_app(runtime=SyntheticRuntime()),
        "POST",
        "/api/predict",
        files={"image": ("synthetic", payload, content_type)},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_IMAGE"


def test_image_above_request_limit_is_rejected() -> None:
    payload = b"x" * (12 * 1024 * 1024 + 1)
    response = _request(
        create_app(runtime=SyntheticRuntime()),
        "POST",
        "/api/predict",
        files={"image": ("synthetic.png", payload, "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "IMAGE_TOO_LARGE"


def test_decoded_dimensions_above_limit_are_rejected() -> None:
    response = _request(
        create_app(runtime=SyntheticRuntime()),
        "POST",
        "/api/predict",
        files={"image": ("synthetic.png", _png_bytes(width=8193, height=1), "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_IMAGE"


def test_inference_failure_suppresses_private_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    sentinel = "C:" + "\\Users\\private\\model.onnx::synthetic-private-token"

    class FailingRuntime(SyntheticRuntime):
        def predict(self, image: Image.Image) -> PredictionResult:
            raise RuntimeError(sentinel)

    response = _request(
        create_app(runtime=FailingRuntime()),
        "POST",
        "/api/predict",
        files={"image": ("synthetic.png", _png_bytes(), "image/png")},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "INFERENCE_FAILED",
            "message": "分割推論失敗，未保留上傳內容。",
        }
    }
    captured = capsys.readouterr()
    assert sentinel not in response.text
    assert sentinel not in captured.out
    assert sentinel not in captured.err


def test_missing_calibration_remains_local_review_with_safe_status() -> None:
    status = replace(READY_STATUS, calibration_available=False, model_sha256_prefix=None)
    response = _request(
        create_app(runtime=SyntheticRuntime(status)),
        "GET",
        "/api/model-status",
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "local_review"
    assert response.json()["calibration_available"] is False
    assert response.json()["model_sha256_prefix"] is None
