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
