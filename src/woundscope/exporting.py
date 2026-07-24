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
    rtol: float = 1e-3,
    atol: float = 1e-4,
) -> dict[str, Any]:
    model = model.cpu().eval()
    inputs = inputs.detach().cpu().float()
    with torch.inference_mode():
        torch_logits = model(inputs).numpy()
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_logits = session.run(["logits"], {"image": inputs.numpy()})[0]
    close = bool(np.allclose(torch_logits, onnx_logits, rtol=rtol, atol=atol))
    torch_mask = 1 / (1 + np.exp(-torch_logits)) >= threshold
    onnx_mask = 1 / (1 + np.exp(-onnx_logits)) >= threshold
    masks_equal = bool(np.array_equal(torch_mask, onnx_mask))
    return {
        "allclose": close,
        "masks_equal": masks_equal,
        "max_abs_error": float(np.max(np.abs(torch_logits - onnx_logits))),
        "rtol": rtol,
        "atol": atol,
    }
