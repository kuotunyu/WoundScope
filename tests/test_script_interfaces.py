from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
        ("scripts/build_huggingface_space_bundle.py", "--output-dir"),
        ("scripts/export_onnx.py", "--report"),
        ("scripts/verify_results_bundle.py", "--expected-source-commit"),
        ("scripts/run_colab_pipeline.py", "--source-commit"),
        ("scripts/resume_colab_postprocessing.py", "--implementation-source-commit"),
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


def test_postprocessing_cli_rejects_implementation_commit_not_bound_to_manifest(
    tmp_path: Path,
) -> None:
    (tmp_path / "bundle_manifest.json").write_text(
        json.dumps({"kind": "source", "schema_version": 1, "source_commit": "c" * 40}),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resume_colab_postprocessing.py",
            "--project-root",
            str(tmp_path),
            "--data-dir",
            str(tmp_path / "data"),
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--source-commit",
            "a" * 40,
            "--implementation-source-commit",
            "b" * 40,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert completed.returncode != 0
    assert "does not match" in completed.stderr
