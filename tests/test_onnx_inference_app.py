from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn

import woundscope.exporting as exporting
import woundscope.gradio_app as gradio_app
from woundscope.benchmarking import benchmark_onnx
from woundscope.calibration import CalibrationArtifact
from woundscope.demo import process_for_demo
from woundscope.exporting import export_onnx, onnx_parity
from woundscope.gradio_app import build_demo
from woundscope.inference import OnnxPredictor, TorchPredictor
from woundscope.models import TinyUNet


class _CenterLogitModel(nn.Module):
    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        logits = torch.full(
            (inputs.shape[0], 1, inputs.shape[2], inputs.shape[3]),
            -8.0,
            device=inputs.device,
        )
        height, width = inputs.shape[-2:]
        logits[:, :, height // 4 : 3 * height // 4, width // 4 : 3 * width // 4] = 8.0
        return logits


def _calibration() -> CalibrationArtifact:
    return CalibrationArtifact(
        temperature=1.0,
        threshold=0.5,
        confidence_cutoff=0.4,
        checkpoint_sha256="synthetic",
        config_hash="synthetic",
    )


def test_torch_predictor_restores_original_size_and_demo_outputs() -> None:
    image = Image.fromarray(np.full((40, 64, 3), 120, dtype=np.uint8), mode="RGB")
    predictor = TorchPredictor(_CenterLogitModel(), _calibration(), image_size=64)

    result = predictor.predict(image)
    outputs = process_for_demo(image, predictor)

    assert result.mask.shape == (40, 64)
    assert 0 < result.wound_pixel_ratio < 1
    assert not result.confidence.low_confidence
    assert outputs[0].size == image.size
    assert outputs[1].size == image.size
    assert outputs[2].endswith("%")
    assert "模型分割信心" in outputs[3]


def test_missing_calibration_always_requests_review() -> None:
    image = Image.fromarray(np.full((32, 32, 3), 100, dtype=np.uint8), mode="RGB")
    result = TorchPredictor(_CenterLogitModel(), None, image_size=32).predict(image)

    assert result.confidence.low_confidence
    assert "calibration_metadata_missing_or_incompatible" in result.confidence.reasons


def test_onnx_export_parity_and_predictor(tmp_path: Path) -> None:
    torch.set_num_threads(1)
    model = TinyUNet(base_channels=2).eval()
    path = export_onnx(model, tmp_path / "tiny.onnx", image_size=32)
    inputs = torch.rand((1, 3, 32, 32), generator=torch.Generator().manual_seed(42))

    parity = onnx_parity(model, path, inputs)
    predictor = OnnxPredictor(path, _calibration(), image_size=32)
    image = Image.fromarray(np.full((24, 40, 3), 120, dtype=np.uint8), mode="RGB")
    result = predictor.predict(image)
    benchmark = benchmark_onnx(path, image_size=32, warmup=0, iterations=2)

    assert parity["allclose"]
    assert parity["masks_equal"]
    assert result.mask.shape == (24, 40)
    assert benchmark["backend"] == "onnxruntime"
    assert benchmark["requested_device"] == "cpu"
    assert benchmark["latency_ms"]["p95"] >= 0


def test_onnx_parity_accepts_only_negligible_threshold_crossing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch_logits = torch.full((1, 1, 512, 512), 0.09)
    torch_logits[0, 0, 0, 0] = 0.08
    onnx_logits = np.full((1, 1, 512, 512), 0.09, dtype=np.float32)
    onnx_logits[0, 0, 0, 0] = 0.080387

    class FixedModel(nn.Module):
        def forward(self, _inputs: torch.Tensor) -> torch.Tensor:
            return torch_logits

    class FixedSession:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *_args, **_kwargs):
            return [onnx_logits]

    monkeypatch.setattr(exporting.ort, "InferenceSession", FixedSession)
    threshold = float(torch.sigmoid(torch.tensor(0.0802)))
    parity = onnx_parity(
        FixedModel(), "synthetic.onnx", torch.zeros((1, 3, 512, 512)), threshold=threshold
    )

    assert parity["logits_allclose"] is False
    assert parity["probabilities_allclose"] is True
    assert parity["masks_equal"] is False
    assert parity["masks_equivalent"] is True
    assert parity["material_mask_mismatch_count"] == 0
    assert parity["parity_passed"] is True
    assert parity["max_abs_probability_error"] < 1e-4


def test_onnx_parity_rejects_excessive_near_threshold_mask_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch_logits = torch.full((1, 1, 16, 16), 0.08)
    onnx_logits = np.full((1, 1, 16, 16), 0.080387, dtype=np.float32)

    class FixedModel(nn.Module):
        def forward(self, _inputs: torch.Tensor) -> torch.Tensor:
            return torch_logits

    class FixedSession:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *_args, **_kwargs):
            return [onnx_logits]

    monkeypatch.setattr(exporting.ort, "InferenceSession", FixedSession)
    threshold = float(torch.sigmoid(torch.tensor(0.0802)))
    parity = onnx_parity(
        FixedModel(), "synthetic.onnx", torch.zeros((1, 3, 16, 16)), threshold=threshold
    )

    assert parity["material_mask_mismatch_count"] == 0
    assert parity["mask_mismatch_fraction"] == 1.0
    assert parity["masks_equivalent"] is False
    assert parity["parity_passed"] is False


def test_onnx_parity_converts_calibrated_threshold_to_equivalent_raw_probability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch_logits = torch.full((1, 1, 1, 1), 0.2)
    onnx_logits = np.full((1, 1, 1, 1), 0.2, dtype=np.float32)

    class FixedModel(nn.Module):
        def forward(self, _inputs: torch.Tensor) -> torch.Tensor:
            return torch_logits

    class FixedSession:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *_args, **_kwargs):
            return [onnx_logits]

    monkeypatch.setattr(exporting.ort, "InferenceSession", FixedSession)
    parity = onnx_parity(
        FixedModel(),
        "synthetic.onnx",
        torch.zeros((1, 3, 1, 1)),
        threshold=0.6,
        temperature=0.5,
    )

    expected = float(torch.sigmoid(torch.tensor(0.5 * np.log(0.6 / 0.4))))
    assert parity["raw_probability_threshold"] == pytest.approx(expected)
    assert parity["temperature"] == 0.5
    assert parity["parity_passed"] is True


def test_onnx_parity_rejects_material_probability_and_mask_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch_logits = torch.full((1, 1, 1, 1), -0.02)
    onnx_logits = np.full((1, 1, 1, 1), 0.02, dtype=np.float32)

    class FixedModel(nn.Module):
        def forward(self, _inputs: torch.Tensor) -> torch.Tensor:
            return torch_logits

    class FixedSession:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *_args, **_kwargs):
            return [onnx_logits]

    monkeypatch.setattr(exporting.ort, "InferenceSession", FixedSession)
    parity = onnx_parity(FixedModel(), "synthetic.onnx", torch.zeros((1, 3, 1, 1)))

    assert parity["probabilities_allclose"] is False
    assert parity["masks_equivalent"] is False
    assert parity["material_mask_mismatch_count"] == 1
    assert parity["parity_passed"] is False


def test_gradio_demo_builds_without_loading_model() -> None:
    demo = build_demo()

    assert demo is not None


def test_gradio_demo_uses_private_upload_only_defaults() -> None:
    demo = build_demo()
    image_components = [
        component for component in demo.config["components"] if component["type"] == "image"
    ]
    markdown = "\n".join(
        component["props"].get("value", "")
        for component in demo.config["components"]
        if component["type"] == "markdown"
    )

    assert demo.analytics_enabled is False
    assert demo.delete_cache == (600, 600)
    assert image_components[0]["props"]["sources"] == ["upload"]
    assert all(component["props"]["buttons"] == ["fullscreen"] for component in image_components)
    assert all(
        dependency["api_visibility"] == "private" for dependency in demo.config["dependencies"]
    )
    assert "請勿上傳任何可識別個人的健康資訊" in markdown
    assert "Patient Health Information (PHI)" in markdown
    assert "不構成臨床診斷" in markdown


@pytest.mark.parametrize("revision", ["", "main", "master", "v0.1.0", "ABCDEF"])
def test_remote_model_requires_immutable_commit_revision(
    monkeypatch: pytest.MonkeyPatch, revision: str
) -> None:
    def unexpected_download(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("remote download must not run before revision validation")

    monkeypatch.delenv("WOUNDSCOPE_MODEL_PATH", raising=False)
    monkeypatch.setenv("HF_MODEL_ID", "owner/private-model")
    monkeypatch.setenv("HF_MODEL_REVISION", revision)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", unexpected_download)

    with pytest.raises(RuntimeError, match="40-character"):
        gradio_app._resolve_model_artifacts()


def test_remote_model_uses_one_immutable_revision_without_printing_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[dict[str, object]] = []
    model = tmp_path / "model.onnx"
    calibration = tmp_path / "calibration.json"
    model.write_bytes(b"onnx")
    calibration.write_text("{}", encoding="utf-8")

    def fake_download(model_id: str, *, filename: str, revision: str, token: str | None) -> str:
        calls.append(
            {"model_id": model_id, "filename": filename, "revision": revision, "token": token}
        )
        return str(model if filename == "model.onnx" else calibration)

    monkeypatch.delenv("WOUNDSCOPE_MODEL_PATH", raising=False)
    monkeypatch.setenv("HF_MODEL_ID", "owner/private-model")
    monkeypatch.setenv("HF_MODEL_REVISION", "a" * 40)
    monkeypatch.setenv("HF_TOKEN", "test-private-token")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", fake_download)

    resolved = gradio_app._resolve_model_artifacts()

    assert resolved == (model, calibration)
    assert [call["revision"] for call in calls] == ["a" * 40, "a" * 40]
    captured = capsys.readouterr()
    assert "test-private-token" not in captured.out
    assert "test-private-token" not in captured.err


def test_remote_model_download_error_suppresses_token_bearing_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    token = "synthetic-private-token-sentinel"

    def failing_download(
        _model_id: str,
        *,
        filename: str,
        revision: str,
        token: str | None,
    ) -> str:
        raise RuntimeError(f"download failed for {filename} at {revision} with credential {token}")

    monkeypatch.delenv("WOUNDSCOPE_MODEL_PATH", raising=False)
    monkeypatch.setenv("HF_MODEL_ID", "owner/private-model")
    monkeypatch.setenv("HF_MODEL_REVISION", "a" * 40)
    monkeypatch.setenv("HF_TOKEN", token)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", failing_download)

    with pytest.raises(
        RuntimeError,
        match=r"^Pinned Hugging Face model download failed\.$",
    ) as error:
        gradio_app._resolve_model_artifacts()

    rendered = "".join(traceback.format_exception(error.type, error.value, error.tb))
    captured = capsys.readouterr()
    assert token not in rendered
    assert token not in captured.out
    assert token not in captured.err
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
