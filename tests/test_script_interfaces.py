from __future__ import annotations

import subprocess
import sys

import pytest


def test_train_cli_exposes_forced_resume_gate() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/train.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert "--stop-after-epoch" in completed.stdout


@pytest.mark.parametrize(
    ("script", "required_option"),
    [
        ("scripts/build_colab_bundle.py", "--verify"),
        ("scripts/export_onnx.py", "--report"),
        ("scripts/verify_results_bundle.py", "--expected-source-commit"),
        ("scripts/run_colab_pipeline.py", "--source-commit"),
    ],
)
def test_staged_pipeline_scripts_expose_locked_interfaces(
    script: str, required_option: str
) -> None:
    completed = subprocess.run(
        [sys.executable, script, "--help"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert required_option in completed.stdout
