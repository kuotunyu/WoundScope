"""WoundScope Gradio UI with lazy model loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import gradio as gr

from woundscope.calibration import CalibrationArtifact
from woundscope.demo import process_for_demo
from woundscope.inference import OnnxPredictor


def _resolve_model_artifacts() -> tuple[Path, Path]:
    model_path = Path(os.environ.get("WOUNDSCOPE_MODEL_PATH", "artifacts/exports/model.onnx"))
    calibration_path = Path(
        os.environ.get("WOUNDSCOPE_CALIBRATION_PATH", "artifacts/calibration.json")
    )
    if model_path.is_file():
        return model_path, calibration_path
    model_id = os.environ.get("HF_MODEL_ID", "").strip()
    if not model_id:
        return model_path, calibration_path
    from huggingface_hub import hf_hub_download

    revision = os.environ.get("HF_MODEL_REVISION", "main")
    token = os.environ.get("HF_TOKEN") or None
    model_path = Path(
        hf_hub_download(
            model_id,
            filename=os.environ.get("HF_MODEL_FILENAME", "model.onnx"),
            revision=revision,
            token=token,
        )
    )
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


@lru_cache(maxsize=1)
def _load_predictor() -> OnnxPredictor:
    model_path, calibration_path = _resolve_model_artifacts()
    if not model_path.is_file():
        raise FileNotFoundError(
            f"找不到 ONNX model：{model_path}。請先匯出模型或設定 WOUNDSCOPE_MODEL_PATH。"
        )
    calibration = CalibrationArtifact.load(calibration_path) if calibration_path.is_file() else None
    return OnnxPredictor(model_path, calibration, device="cpu")


def _predict(image):
    return process_for_demo(image, _load_predictor())


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="WoundScope") as demo:
        gr.Markdown(
            """
            # WoundScope

            足部潰瘍區域 segmentation 研究展示。輸出不是疾病診斷、嚴重度或治療建議，
            不可取代醫師或傷口照護專業人員判斷。低信心與所有其他結果都需人工複核。

            Data source: Foot Ulcer Segmentation Challenge (FUSeg), UWM Big Data Lab.
            """
        )
        input_image = gr.Image(type="pil", label="上傳影像")
        run_button = gr.Button("執行 segmentation", variant="primary")
        with gr.Row():
            original = gr.Image(label="原圖")
            overlay = gr.Image(label="Mask overlay")
        with gr.Row():
            ratio = gr.Textbox(label="傷口像素比例")
            confidence = gr.Textbox(label="模型分割信心")
            timing = gr.Textbox(label="推論時間")
        warning = gr.Textbox(label="人工複核警示")
        run_button.click(
            _predict,
            inputs=[input_image],
            outputs=[original, overlay, ratio, confidence, timing, warning],
        )
    return demo


demo = build_demo()
