from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def test_space_readme_declares_code_only_permission_pending_contract() -> None:
    text = Path("deploy/huggingface/README.md").read_text(encoding="utf-8")
    front_matter = yaml.safe_load(text.split("---", 2)[1])

    assert front_matter["sdk"] == "docker"
    assert front_matter["app_port"] == 7860
    assert front_matter["license"] == "apache-2.0"
    assert "PERMISSION_PENDING" in text
    assert "僅含程式碼" in text
    assert "不得上傳 FUSeg 原始影像、標註或病患相關資料" in text
    assert "目前的 `PERMISSION_PENDING` code-only 階段不使用任何 token" in text
    assert "未來另行核准的 Protected／Private model flow" in text
    assert "最小權限 read-only runtime secret" in text
    assert "runtime 永遠不得使用 write token、私密 URL 或未固定的 revision" in text


def test_space_builder_cli_exposes_safe_output_options() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/build_huggingface_space_bundle.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert "--output-dir" in completed.stdout
    assert "--output-zip" in completed.stdout


def test_deployment_docs_keep_external_actions_permission_gated() -> None:
    guide = Path("docs/huggingface-space-deployment.md").read_text(encoding="utf-8")
    request = Path("docs/permissions/fuseg-model-artifact-permission-request.md").read_text(
        encoding="utf-8"
    )
    readme = Path("README.md").read_text(encoding="utf-8")
    plan = Path("PROJECT_PLAN.md").read_text(encoding="utf-8")

    for required in (
        "PERMISSION_PENDING",
        "Public Space",
        "Protected Space",
        "Private Space",
        "HF_MODEL_REVISION",
        "40-character",
        "rollback",
        "teardown",
    ):
        assert required in guide
    for question in (
        "CC BY-NC",
        "derived model weights",
        "public non-commercial inference",
        "ONNX",
        "attribution",
    ):
        assert question in request
    assert "尚未發送" in request
    assert "收件者：FUSeg dataset maintainer / rights holder\n\n主旨：" in request
    assert "以可保存的書面方式" in request
    assert "可保存的書面回覆" in plan
    assert "Space%20授權確認中" in readme
    assert "docs/huggingface-space-deployment.md" in readme


def test_deployment_guide_exact_inventory_includes_dockerignore() -> None:
    guide = Path("docs/huggingface-space-deployment.md").read_text(encoding="utf-8")
    inventory_line = next(line for line in guide.splitlines() if "候選的**精確 inventory**" in line)

    assert "`.dockerignore`" in inventory_line
