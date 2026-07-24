from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn

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


def test_gradio_demo_builds_without_loading_model() -> None:
    demo = build_demo()

    assert demo is not None
