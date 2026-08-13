from __future__ import annotations

from pathlib import Path

from woundscope.model_runtime import RuntimeMode, inspect_model_status


def _clear_remote_environment(monkeypatch) -> None:
    for name in ("HF_MODEL_ID", "HF_MODEL_REVISION", "HF_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_missing_model_reports_showcase_without_private_path(monkeypatch, tmp_path: Path) -> None:
    private = tmp_path / "private" / "model.onnx"
    calibration = tmp_path / "private" / "calibration.json"
    monkeypatch.setenv("WOUNDSCOPE_MODEL_PATH", str(private))
    monkeypatch.setenv("WOUNDSCOPE_CALIBRATION_PATH", str(calibration))
    _clear_remote_environment(monkeypatch)

    status = inspect_model_status()

    assert status.mode is RuntimeMode.SHOWCASE
    assert status.model_available is False
    assert status.calibration_available is False
    assert status.provider == "unavailable"
    assert str(private) not in status.message
    assert str(calibration) not in status.message


def test_ready_artifacts_report_local_review(monkeypatch, tmp_path: Path) -> None:
    model = tmp_path / "model.onnx"
    calibration = tmp_path / "calibration.json"
    model.write_bytes(b"synthetic")
    calibration.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("WOUNDSCOPE_MODEL_PATH", str(model))
    monkeypatch.setenv("WOUNDSCOPE_CALIBRATION_PATH", str(calibration))
    _clear_remote_environment(monkeypatch)

    status = inspect_model_status()

    assert status.mode is RuntimeMode.LOCAL_REVIEW
    assert status.model_available is True
    assert status.calibration_available is True
    assert status.model_label == "EfficientNet-B0 U-Net / ONNX"
    assert status.provider == "CPUExecutionProvider"
    assert str(model) not in status.message
    assert str(calibration) not in status.message
