from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def test_colab_notebook_has_locked_workflow_cells() -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb").read_text(encoding="utf-8")
    )
    assert notebook["nbformat"] == 4
    sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    required = (
        "drive.mount",
        "torch.cuda.is_available",
        "WoundScope_colab_source.zip",
        "WoundScopeArtifacts",
        "bundle_manifest.json",
        "WOUNDSCOPE_SOURCE_COMMIT",
        "scripts/run_colab_pipeline.py",
        "--source-commit",
        "artifact_base_dir / source_commit[:12]",
        "pipeline_state.json",
    )
    for marker in required:
        assert marker in sources
    forbidden = (
        "RUN_MODE",
        "FULL_STAGE",
        "SELECTED_LOSS_UNET",
        "SELECTED_LOSS_SEGFORMER",
        "scripts/train.py",
        "scripts/evaluate.py",
        "scripts/export_onnx.py",
    )
    for marker in forbidden:
        assert marker not in sources
    assert len(notebook["cells"]) <= 6
    assert notebook["metadata"]["accelerator"] == "GPU"


def test_colab_notebook_resolves_inputs_inside_woundscope_drive_folder(
    tmp_path: Path, monkeypatch
) -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb").read_text(encoding="utf-8")
    )
    drive_mount = tmp_path / "drive"
    source_zip = drive_mount / "MyDrive" / "WoundScope" / "WoundScope_colab_source.zip"
    source_zip.parent.mkdir(parents=True)
    source_zip.write_bytes(b"source bundle placeholder")

    fake_drive = SimpleNamespace(mount=lambda _path: None)
    google_module = ModuleType("google")
    colab_module = ModuleType("google.colab")
    colab_module.drive = fake_drive
    google_module.colab = colab_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.colab", colab_module)
    monkeypatch.setenv("WOUNDSCOPE_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("WOUNDSCOPE_DRIVE_MOUNT", str(drive_mount))
    monkeypatch.chdir(Path.cwd())

    namespace: dict[str, object] = {}
    exec("".join(notebook["cells"][1]["source"]), namespace)

    assert namespace["source_zip"] == source_zip
    assert namespace["artifact_base_dir"] == source_zip.parent / "WoundScopeArtifacts"


def test_colab_notebook_uses_public_v0_1_0_source_when_drive_zip_is_absent(
    tmp_path: Path, monkeypatch
) -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb").read_text(encoding="utf-8")
    )
    drive_mount = tmp_path / "drive"
    drive_project_dir = drive_mount / "MyDrive" / "WoundScope"
    drive_project_dir.mkdir(parents=True)
    resolved_commit = "b" * 40

    fake_drive = SimpleNamespace(mount=lambda _path: None)
    google_module = ModuleType("google")
    colab_module = ModuleType("google.colab")
    colab_module.drive = fake_drive
    google_module.colab = colab_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.colab", colab_module)
    monkeypatch.setenv("WOUNDSCOPE_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("WOUNDSCOPE_DRIVE_MOUNT", str(drive_mount))
    monkeypatch.delenv("WOUNDSCOPE_GIT_URL", raising=False)
    monkeypatch.delenv("WOUNDSCOPE_GIT_REF", raising=False)

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        if command[:2] == ["git", "clone"]:
            assert "https://github.com/kuotunyu/WoundScope.git" in command
            assert command[command.index("--branch") + 1] == "v0.1.0"
            Path(command[-1]).mkdir(parents=True)
            return SimpleNamespace(returncode=0, stdout="")
        if command[-2:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=f"{resolved_commit}\n")
        if command[-2:] == ["status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.chdir(Path.cwd())
    namespace: dict[str, object] = {}

    exec("".join(notebook["cells"][1]["source"]), namespace)
    exec("".join(notebook["cells"][2]["source"]), namespace)

    assert namespace["source_commit"] == resolved_commit
    assert namespace["project_dir"] == tmp_path / "WoundScope_public_source"
    assert namespace["artifact_dir"] == (
        drive_project_dir / "WoundScopeArtifacts" / resolved_commit[:12]
    )


def test_colab_notebook_surfaces_failed_stage_diagnostic(tmp_path: Path, monkeypatch) -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb").read_text(encoding="utf-8")
    )
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "pipeline_state.json").write_text(
        json.dumps(
            {
                "stages": {
                    "quick_gpu": {
                        "status": "failed",
                        "error_type": "RuntimeError",
                        "error": "CUDA OOM diagnostic",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fake_subprocess = SimpleNamespace(run=lambda *_args, **_kwargs: SimpleNamespace(returncode=1))
    namespace = {
        "Path": Path,
        "artifact_dir": artifact_dir,
        "json": json,
        "os": os,
        "project_dir": tmp_path / "project",
        "runtime_root": tmp_path,
        "source_commit": "a" * 40,
        "subprocess": fake_subprocess,
        "sys": sys,
    }
    monkeypatch.delenv("WOUNDSCOPE_DATA_DIR", raising=False)

    with pytest.raises(RuntimeError, match=r"quick_gpu.*CUDA OOM diagnostic"):
        exec("".join(notebook["cells"][4]["source"]), namespace)


def test_colab_notebook_rejects_invalid_source_commit_before_path_construction(
    tmp_path: Path,
) -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb").read_text(encoding="utf-8")
    )
    source_zip = tmp_path / "source.zip"
    manifest = {
        "kind": "source",
        "schema_version": 1,
        "source_commit": "../not-a-git-sha",
        "files": [],
    }
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("bundle_manifest.json", json.dumps(manifest))
    namespace = {
        "artifact_base_dir": tmp_path / "artifacts",
        "os": os,
        "runtime_root": tmp_path / "runtime",
        "source_zip": source_zip,
    }

    with pytest.raises(RuntimeError, match="Invalid source commit"):
        exec("".join(notebook["cells"][2]["source"]), namespace)


def test_postprocessing_recovery_notebook_is_pinned_to_existing_training_artifacts() -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_c7ec606_Postprocess_Resume_Colab.ipynb").read_text(
            encoding="utf-8"
        )
    )
    sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert notebook["metadata"]["accelerator"] == "GPU"
    assert "c7ec6060f1bd0a813a890b95b50c2855d3c2640c" in sources
    assert "scripts/resume_colab_postprocessing.py" in sources
    assert "--implementation-source-commit" in sources
    assert "artifact_base_dir / training_source_commit[:12]" in sources
    assert "scripts/run_colab_pipeline.py" not in sources
    assert "scripts/train.py" not in sources
    assert "record.get('implementation_source_commit') == implementation_source_commit" in sources
    assert "record != before_stage_records.get(stage)" in sources
    assert "subprocess.Popen" in sources
    assert "Last subprocess output" in sources


def test_postprocessing_recovery_notebook_reuses_c7_artifact_directory(tmp_path: Path) -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_c7ec606_Postprocess_Resume_Colab.ipynb").read_text(
            encoding="utf-8"
        )
    )
    source_zip = tmp_path / "WoundScope_colab_source.zip"
    implementation_commit = "b" * 40
    manifest = {
        "kind": "source",
        "schema_version": 1,
        "source_commit": implementation_commit,
        "files": [],
    }
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("bundle_manifest.json", json.dumps(manifest))
    artifact_base_dir = tmp_path / "WoundScopeArtifacts"
    c7_artifacts = artifact_base_dir / "c7ec6060f1bd"
    c7_artifacts.mkdir(parents=True)
    (c7_artifacts / "pipeline_state.json").write_text("{}", encoding="utf-8")
    namespace = {
        "artifact_base_dir": artifact_base_dir,
        "os": os,
        "runtime_root": tmp_path / "runtime",
        "source_zip": source_zip,
    }
    namespace["runtime_root"].mkdir()

    exec("".join(notebook["cells"][2]["source"]), namespace)

    assert namespace["training_source_commit"] == "c7ec6060f1bd0a813a890b95b50c2855d3c2640c"
    assert namespace["implementation_source_commit"] == implementation_commit
    assert namespace["artifact_dir"] == c7_artifacts


def test_postprocessing_recovery_notebook_does_not_report_stale_same_commit_failure(
    tmp_path: Path,
) -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_c7ec606_Postprocess_Resume_Colab.ipynb").read_text(
            encoding="utf-8"
        )
    )
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    state_path = artifact_dir / "pipeline_state.json"
    implementation_commit = "b" * 40
    state_path.write_text(
        json.dumps(
            {
                "stages": {
                    "onnx_and_benchmark": {
                        "status": "failed",
                        "implementation_source_commit": implementation_commit,
                        "error_type": "RuntimeError",
                        "error": "stale first-attempt error",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    fake_process = SimpleNamespace(
        stdout=iter(["preflight root cause\n"]),
        wait=lambda: 1,
    )
    fake_subprocess = SimpleNamespace(
        PIPE=object(),
        STDOUT=object(),
        Popen=lambda *_args, **_kwargs: fake_process,
    )
    namespace = {
        "Path": Path,
        "artifact_dir": artifact_dir,
        "implementation_source_commit": implementation_commit,
        "json": json,
        "os": os,
        "project_dir": tmp_path / "project",
        "runtime_root": tmp_path,
        "state_path": state_path,
        "subprocess": fake_subprocess,
        "sys": sys,
        "training_source_commit": "c7ec6060f1bd0a813a890b95b50c2855d3c2640c",
    }

    with pytest.raises(RuntimeError, match="exited with code 1") as error:
        exec("".join(notebook["cells"][4]["source"]), namespace)

    assert "stale first-attempt error" not in str(error.value)
    assert "preflight root cause" in str(error.value)


def test_release_files_and_result_markers_exist() -> None:
    expected = (
        ".github/workflows/ci.yml",
        "Dockerfile",
        "MODEL_CARD.md",
        "DATA_CARD.md",
        "CITATION.cff",
        ".env.example",
        "scripts/download_artifacts.md",
    )
    for path in expected:
        assert Path(path).is_file()
    readme = Path("README.md").read_text(encoding="utf-8")
    assert readme.count("<!-- RESULTS_TABLE_START -->") == 1
    assert readme.count("<!-- RESULTS_TABLE_END -->") == 1
