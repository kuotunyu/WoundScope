from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn

import woundscope.exporting as exporting
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
