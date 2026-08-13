"""Safe model-artifact resolution shared by local presentation layers."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from woundscope.calibration import CalibrationArtifact
from woundscope.inference import OnnxPredictor

IMMUTABLE_HF_REVISION = re.compile(r"[0-9a-f]{40}")
MODEL_LABEL = "EfficientNet-B0 U-Net / ONNX"


class RuntimeMode(StrEnum):
    SHOWCASE = "showcase"
    LOCAL_REVIEW = "local_review"


@dataclass(frozen=True)
class ModelStatus:
    mode: RuntimeMode
    model_available: bool
    calibration_available: bool
    model_label: str
    provider: str
    message: str
    model_sha256_prefix: str | None = None


def _configured_artifact_paths() -> tuple[Path, Path]:
    return (
        Path(os.environ.get("WOUNDSCOPE_MODEL_PATH", "artifacts/exports/model.onnx")),
        Path(
            os.environ.get(
                "WOUNDSCOPE_CALIBRATION_PATH",
                "artifacts/calibration.json",
            )
        ),
    )


def _require_immutable_hf_revision() -> str:
    revision = os.environ.get("HF_MODEL_REVISION", "").strip()
    if IMMUTABLE_HF_REVISION.fullmatch(revision) is None:
        raise RuntimeError("HF_MODEL_REVISION must be a 40-character lowercase Git commit SHA.")
    return revision


def resolve_model_artifacts() -> tuple[Path, Path]:
    model_path, calibration_path = _configured_artifact_paths()
    if model_path.is_file():
        return model_path, calibration_path
    model_id = os.environ.get("HF_MODEL_ID", "").strip()
    if not model_id:
        return model_path, calibration_path

    from huggingface_hub import hf_hub_download

    revision = _require_immutable_hf_revision()
    token = os.environ.get("HF_TOKEN") or None
    try:
        model_path = Path(
            hf_hub_download(
                model_id,
                filename=os.environ.get("HF_MODEL_FILENAME", "model.onnx"),
                revision=revision,
                token=token,
            )
        )
    except Exception:
        raise RuntimeError("Pinned Hugging Face model download failed.") from None
    try:
        calibration_path = Path(
            hf_hub_download(
                model_id,
                filename=os.environ.get("HF_CALIBRATION_FILENAME", "calibration.json"),
                revision=revision,
                token=token,
            )
        )
    except Exception:
        calibration_path = Path("__missing_calibration__.json")
    return model_path, calibration_path


def _sha256_prefix(path: Path, length: int = 12) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def inspect_model_status() -> ModelStatus:
    """Inspect configured local files without loading or downloading a model."""
    model_path, calibration_path = _configured_artifact_paths()
    if not model_path.is_file():
        return ModelStatus(
            mode=RuntimeMode.SHOWCASE,
            model_available=False,
            calibration_available=False,
            model_label=MODEL_LABEL,
            provider="unavailable",
            message="目前為研究展示模式；本機模型可用時才開啟分割複核。",
        )

    calibration_available = calibration_path.is_file()
    message = (
        "本機模型與 calibration 已就緒，可進行單張影像分割複核。"
        if calibration_available
        else "本機模型已就緒，但 calibration metadata 缺失；所有結果均需人工複核。"
    )
    return ModelStatus(
        mode=RuntimeMode.LOCAL_REVIEW,
        model_available=True,
        calibration_available=calibration_available,
        model_label=MODEL_LABEL,
        provider="CPUExecutionProvider",
        message=message,
        model_sha256_prefix=_sha256_prefix(model_path),
    )


@lru_cache(maxsize=1)
def load_predictor() -> OnnxPredictor:
    model_path, calibration_path = resolve_model_artifacts()
    if not model_path.is_file():
        raise FileNotFoundError("找不到可用的 ONNX model。請先設定本機 model artifact。")
    calibration = CalibrationArtifact.load(calibration_path) if calibration_path.is_file() else None
    return OnnxPredictor(model_path, calibration, device="cpu")
