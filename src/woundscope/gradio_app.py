"""WoundScope Gradio UI with lazy model loading."""

from __future__ import annotations

import gradio as gr

from woundscope.demo import process_for_demo
from woundscope.model_runtime import load_predictor, resolve_model_artifacts

_resolve_model_artifacts = resolve_model_artifacts
_load_predictor = load_predictor


def _predict(image):
    return process_for_demo(image, _load_predictor())


def build_demo() -> gr.Blocks:
    with gr.Blocks(
        title="WoundScope",
        analytics_enabled=False,
        delete_cache=(600, 600),
    ) as demo:
        gr.Markdown(
            """
            # WoundScope

            足部潰瘍區域 segmentation 研究展示。輸出不是疾病診斷、嚴重度或治療建議，
            不可取代醫師或傷口照護專業人員判斷。低信心與所有其他結果都需人工複核。

            Data source: Foot Ulcer Segmentation Challenge (FUSeg), UWM Big Data Lab.
            """
        )
        input_image = gr.Image(
            type="pil",
            label="上傳影像",
            sources=["upload"],
            buttons=["fullscreen"],
        )
        run_button = gr.Button("執行 segmentation", variant="primary")
        gr.Markdown(
            "請勿上傳任何可識別個人的健康資訊，包括 Patient Health Information (PHI)。"
            "本工具僅供研究與技術展示，不構成臨床診斷、嚴重度判定、預後或治療建議；"
            "系統不記錄檔名或影像內容。"
        )
        with gr.Row():
            original = gr.Image(label="原圖", interactive=False, buttons=["fullscreen"])
            overlay = gr.Image(label="Mask overlay", interactive=False, buttons=["fullscreen"])
        with gr.Row():
            ratio = gr.Textbox(label="傷口像素比例")
            confidence = gr.Textbox(label="模型分割信心")
            timing = gr.Textbox(label="推論時間")
        warning = gr.Textbox(label="人工複核警示")
        run_button.click(
            _predict,
            inputs=[input_image],
            outputs=[original, overlay, ratio, confidence, timing, warning],
            api_visibility="private",
        )
    return demo


demo = build_demo()
