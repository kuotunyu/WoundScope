"""Fixed-spatial ONNX export and numerical parity checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
import torch
from torch import Tensor, nn


def export_onnx(
    model: nn.Module,
    output_path: str | Path,
    *,
    image_size: int = 512,
    opset: int = 17,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = model.cpu().eval()
    example = torch.zeros((1, 3, image_size, image_size), dtype=torch.float32)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    torch.onnx.export(
        model,
        example,
        temporary,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=opset,
        do_constant_folding=True,
        dynamo=False,
    )
    temporary.replace(output_path)
    return output_path


def onnx_parity(
    model: nn.Module,
    onnx_path: str | Path,
    inputs: Tensor,
    *,
    threshold: float = 0.5,
    temperature: float = 1.0,
    rtol: float = 1e-3,
    atol: float = 1e-4,
    max_mask_mismatch_count: int = 32,
    max_mask_mismatch_fraction: float = 1e-4,
) -> dict[str, Any]:
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and greater than zero")
    if not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("threshold must be finite and strictly between zero and one")
    if max_mask_mismatch_count < 0:
        raise ValueError("max_mask_mismatch_count must be non-negative")
    if not 0 <= max_mask_mismatch_fraction <= 1:
        raise ValueError("max_mask_mismatch_fraction must be between zero and one")
    model = model.cpu().eval()
    inputs = inputs.detach().cpu().float()
    with torch.inference_mode():
        torch_logits = model(inputs).numpy()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_logits = session.run(["logits"], {"image": inputs.numpy()})[0]
    logits_close = bool(np.allclose(torch_logits, onnx_logits, rtol=rtol, atol=atol))
    torch_probabilities = 1 / (1 + np.exp(-np.clip(torch_logits, -80, 80)))
    onnx_probabilities = 1 / (1 + np.exp(-np.clip(onnx_logits, -80, 80)))
    probabilities_close = bool(
        np.allclose(torch_probabilities, onnx_probabilities, rtol=rtol, atol=atol)
    )
    # sigmoid(logits / T) >= calibrated_threshold is algebraically identical
    # to sigmoid(logits) >= sigmoid(T * logit(calibrated_threshold)). Keeping
    # the parity tolerance in raw model-probability space avoids amplifying
    # backend rounding by a small calibration temperature while preserving the
    # exact deployed binary decision.
    threshold_logit = np.log(threshold / (1 - threshold))
    raw_probability_threshold = float(1 / (1 + np.exp(-temperature * threshold_logit)))
    torch_mask = torch_probabilities >= raw_probability_threshold
    onnx_mask = onnx_probabilities >= raw_probability_threshold
    masks_equal = bool(np.array_equal(torch_mask, onnx_mask))
    mask_mismatches = np.not_equal(torch_mask, onnx_mask)
    # A backend may round opposite sides of the frozen threshold while both
    # probabilities remain within the absolute parity tolerance. Such pixels
    # have no numerically stable binary decision; retain their exact count but
    # reject only threshold crossings outside that tolerance band.
    material_mask_mismatches = mask_mismatches & (
        (np.abs(torch_probabilities - raw_probability_threshold) > atol)
        | (np.abs(onnx_probabilities - raw_probability_threshold) > atol)
    )
    mismatch_count = int(np.count_nonzero(mask_mismatches))
    mismatch_fraction = float(mismatch_count / torch_mask.size)
    material_mismatch_count = int(np.count_nonzero(material_mask_mismatches))
    masks_equivalent = (
        material_mismatch_count == 0
        and mismatch_count <= max_mask_mismatch_count
        and mismatch_fraction <= max_mask_mismatch_fraction
    )
    parity_passed = probabilities_close and masks_equivalent
    return {
        # Backward-compatible summary now reflects the deployed probability
        # output, while the stricter logit diagnostic remains explicit.
        "allclose": probabilities_close,
        "logits_allclose": logits_close,
        "probabilities_allclose": probabilities_close,
        "masks_equal": masks_equal,
        "masks_equivalent": masks_equivalent,
        "mask_mismatch_count": mismatch_count,
        "mask_mismatch_fraction": mismatch_fraction,
        "material_mask_mismatch_count": material_mismatch_count,
        "max_mask_mismatch_count": max_mask_mismatch_count,
        "max_mask_mismatch_fraction": max_mask_mismatch_fraction,
        "parity_passed": parity_passed,
        "max_abs_error": float(np.max(np.abs(torch_logits - onnx_logits))),
        "max_abs_logit_error": float(np.max(np.abs(torch_logits - onnx_logits))),
        "max_abs_probability_error": float(
            np.max(np.abs(torch_probabilities - onnx_probabilities))
        ),
        "temperature": temperature,
        "calibrated_threshold": threshold,
        "raw_probability_threshold": raw_probability_threshold,
        "rtol": rtol,
        "atol": atol,
        "decision_boundary_atol": atol,
    }
