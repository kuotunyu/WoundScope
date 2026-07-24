"""Portable PyTorch/ONNX inference with calibrated two-view uncertainty."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
import onnxruntime as ort
import torch
from PIL import Image
from torch import nn

from woundscope.calibration import CalibrationArtifact
from woundscope.uncertainty import ConfidenceResult, tta_confidence

IMAGENET_MEAN = np.array((0.485, 0.456, 0.406), dtype=np.float32)
IMAGENET_STD = np.array((0.229, 0.224, 0.225), dtype=np.float32)


@dataclass(frozen=True)
class LetterboxMetadata:
    original_width: int
    original_height: int
    resized_width: int
    resized_height: int
    left: int
    top: int


@dataclass(frozen=True)
class PredictionResult:
    mask: np.ndarray
    probability: np.ndarray
    wound_pixel_ratio: float
    confidence: ConfidenceResult
    inference_seconds: float


class Predictor(Protocol):
    def predict(self, image: Image.Image) -> PredictionResult: ...


def preprocess_image(
    image: Image.Image, image_size: int = 512
) -> tuple[np.ndarray, LetterboxMetadata]:
    image = image.convert("RGB")
    original_width, original_height = image.size
    scale = min(image_size / original_width, image_size / original_height)
    resized_width = max(1, round(original_width * scale))
    resized_height = max(1, round(original_height * scale))
    resized = np.asarray(
        image.resize((resized_width, resized_height), Image.Resampling.BILINEAR),
        dtype=np.float32,
    )
    canvas = np.zeros((image_size, image_size, 3), dtype=np.float32)
    left = (image_size - resized_width) // 2
    top = (image_size - resized_height) // 2
    canvas[top : top + resized_height, left : left + resized_width] = resized
    normalized = (canvas / 255.0 - IMAGENET_MEAN) / IMAGENET_STD
    tensor = normalized.transpose(2, 0, 1)[None].astype(np.float32)
    return tensor, LetterboxMetadata(
        original_width,
        original_height,
        resized_width,
        resized_height,
        left,
        top,
    )


def restore_probability(probability: np.ndarray, metadata: LetterboxMetadata) -> np.ndarray:
    cropped = probability[
        metadata.top : metadata.top + metadata.resized_height,
        metadata.left : metadata.left + metadata.resized_width,
    ]
    return cv2.resize(
        cropped,
        (metadata.original_width, metadata.original_height),
        interpolation=cv2.INTER_LINEAR,
    )


def _sigmoid(logits: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(logits, -80, 80)))


class _BasePredictor:
    def __init__(
        self,
        calibration: CalibrationArtifact | None,
        *,
        image_size: int = 512,
    ) -> None:
        self.calibration = calibration
        self.image_size = image_size

    def _run_logits(self, tensor: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def predict(self, image: Image.Image) -> PredictionResult:
        tensor, metadata = preprocess_image(image, self.image_size)
        started = time.perf_counter()
        original_logits = self._run_logits(tensor)[0, 0]
        flipped_input = np.flip(tensor, axis=3).copy()
        flipped_logits = np.flip(self._run_logits(flipped_input)[0, 0], axis=1).copy()
        elapsed = time.perf_counter() - started
        calibration_valid = self.calibration is not None
        temperature = self.calibration.temperature if self.calibration else 1.0
        threshold = self.calibration.threshold if self.calibration else 0.5
        cutoff = self.calibration.confidence_cutoff if self.calibration else 1.0
        original_probability = restore_probability(
            _sigmoid(original_logits / temperature), metadata
        )
        flipped_probability = restore_probability(_sigmoid(flipped_logits / temperature), metadata)
        mean_probability = (original_probability + flipped_probability) / 2
        mask = mean_probability >= threshold
        confidence = tta_confidence(
            original_probability,
            flipped_probability,
            threshold=threshold,
            cutoff=cutoff,
            calibration_valid=calibration_valid,
        )
        return PredictionResult(
            mask=mask,
            probability=mean_probability,
            wound_pixel_ratio=float(np.mean(mask)),
            confidence=confidence,
            inference_seconds=elapsed,
        )


class TorchPredictor(_BasePredictor):
    def __init__(
        self,
        model: nn.Module,
        calibration: CalibrationArtifact | None,
        *,
        device: str = "cpu",
        image_size: int = 512,
    ) -> None:
        super().__init__(calibration, image_size=image_size)
        self.device = torch.device(device)
        self.model = model.to(self.device).eval()

    def _run_logits(self, tensor: np.ndarray) -> np.ndarray:
        with torch.inference_mode():
            return self.model(torch.from_numpy(tensor).to(self.device)).detach().cpu().numpy()


class OnnxPredictor(_BasePredictor):
    def __init__(
        self,
        model_path: str | Path,
        calibration: CalibrationArtifact | None,
        *,
        device: str = "cpu",
        image_size: int = 512,
    ) -> None:
        super().__init__(calibration, image_size=image_size)
        available = ort.get_available_providers()
        if device == "auto":
            device = "cuda" if "CUDAExecutionProvider" in available else "cpu"
        if device == "cuda" and "CUDAExecutionProvider" not in available:
            raise RuntimeError("ONNX Runtime CUDAExecutionProvider is not available")
        if device not in {"cpu", "cuda"}:
            raise ValueError(f"Unsupported ONNX device: {device}")
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if device == "cuda"
            else ["CPUExecutionProvider"]
        )
        self.session = ort.InferenceSession(str(model_path), providers=providers)

    def _run_logits(self, tensor: np.ndarray) -> np.ndarray:
        return self.session.run(["logits"], {"image": tensor})[0]


def create_overlay(image: Image.Image, mask: np.ndarray, alpha: float = 0.4) -> Image.Image:
    original = np.asarray(image.convert("RGB"), dtype=np.float32)
    if mask.shape != original.shape[:2]:
        raise ValueError("Mask must be restored to the original image size")
    color = np.zeros_like(original)
    color[..., 0] = 255
    blended = original.copy()
    blended[mask] = (1 - alpha) * original[mask] + alpha * color[mask]
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), mode="RGB")
