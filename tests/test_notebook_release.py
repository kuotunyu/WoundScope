from __future__ import annotations

import json
from pathlib import Path


def test_colab_notebook_has_locked_workflow_cells() -> None:
    notebook = json.loads(Path("notebooks/01_train_colab.ipynb").read_text(encoding="utf-8"))
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
    assert "待填" in readme
