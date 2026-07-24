"""Machine-readable ONNX Runtime latency benchmarking."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort


def benchmark_onnx(
    model_path: str | Path,
    *,
    device: str = "cpu",
    image_size: int = 512,
    warmup: int = 10,
    iterations: int = 50,
) -> dict[str, Any]:
    if warmup < 0 or iterations <= 0:
        raise ValueError("warmup must be non-negative and iterations must be positive")
    available = ort.get_available_providers()
    if device == "auto":
        device = "cuda" if "CUDAExecutionProvider" in available else "cpu"
    if device == "cuda" and "CUDAExecutionProvider" not in available:
        raise RuntimeError("ONNX Runtime CUDAExecutionProvider is not available")
    if device not in {"cpu", "cuda"}:
        raise ValueError(f"Unsupported device: {device}")
    providers = (
        ["CUDAExecutionProvider", "CPUExecutionProvider"]
        if device == "cuda"
        else ["CPUExecutionProvider"]
    )
    session = ort.InferenceSession(str(model_path), providers=providers)
    inputs = np.zeros((1, 3, image_size, image_size), dtype=np.float32)
    for _ in range(warmup):
        session.run(["logits"], {"image": inputs})
    timings = []
    for _ in range(iterations):
        started = time.perf_counter()
        session.run(["logits"], {"image": inputs})
        timings.append((time.perf_counter() - started) * 1000)
    return {
        "backend": "onnxruntime",
        "requested_device": device,
        "providers": session.get_providers(),
        "image_size": image_size,
        "warmup": warmup,
        "iterations": iterations,
        "latency_ms": {
            "mean": float(np.mean(timings)),
            "median": float(np.median(timings)),
            "p95": float(np.quantile(timings, 0.95)),
            "min": float(np.min(timings)),
            "max": float(np.max(timings)),
        },
    }
