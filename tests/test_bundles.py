from __future__ import annotations

import importlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest


def _module():
    return importlib.import_module("woundscope.bundles")


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def test_source_bundle_uses_committed_allowlist_and_records_hashes(tmp_path: Path) -> None:
    bundles = _module()
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "src" / "woundscope").mkdir(parents=True)
    (repository / "src" / "woundscope" / "__init__.py").write_text(
        '__version__ = "test"\n', encoding="utf-8"
    )
    (repository / "configs").mkdir()
    (repository / "configs" / "base.yaml").write_text("project: test\n", encoding="utf-8")
    (repository / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    (repository / ".env").write_text("SECRET=never\n", encoding="utf-8")
    (repository / "data").mkdir()
    (repository / "data" / "patient.png").write_bytes(b"private")
    (repository / "docs" / "superpowers").mkdir(parents=True)
    (repository / "docs" / "superpowers" / "notes.md").write_text("local note", encoding="utf-8")
    (repository / "docs" / "huggingface-space-deployment.md").write_text(
        "public deployment guide\n", encoding="utf-8"
    )
    (repository / "deploy" / "huggingface").mkdir(parents=True)
    (repository / "deploy" / "huggingface" / "README.md").write_text(
        "public Space metadata\n", encoding="utf-8"
    )
    (repository / "reports" / "public").mkdir(parents=True)
    (repository / "reports" / "README.md").write_text("public report policy\n", encoding="utf-8")
    (repository / "reports" / "public" / "model_comparison.svg").write_text(
        "<svg><title>aggregate comparison</title></svg>\n", encoding="utf-8"
    )
    (repository / "reports" / "public" / "woundscope-ui-showcase.webp").write_bytes(
        b"RIFFsynthetic-public-showcase"
    )
    (repository / ".dockerignore").write_text("artifacts/\n", encoding="utf-8")
    (repository / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "Test")
    _git(repository, "config", "user.email", "test@example.com")
    _git(
        repository,
        "add",
        "src",
        "configs",
        "pyproject.toml",
        ".dockerignore",
        "SECURITY.md",
        "deploy",
        "docs",
        "reports",
    )
    _git(repository, "commit", "-m", "fixture")
    source_commit = _git(repository, "rev-parse", "HEAD")
    output = tmp_path / "source.zip"

    manifest = bundles.build_source_bundle(repository, output)
    verified = bundles.verify_bundle(output, expected_kind="source")
    extracted = bundles.extract_bundle(output, tmp_path / "extracted", expected_kind="source")

    assert manifest["source_commit"] == source_commit
    assert verified == manifest
    assert extracted == manifest
    assert (tmp_path / "extracted" / "src" / "woundscope" / "__init__.py").is_file()
    names = {entry["path"] for entry in manifest["files"]}
    assert "src/woundscope/__init__.py" in names
    assert "configs/base.yaml" in names
    assert "pyproject.toml" in names
    assert ".dockerignore" in names
    assert "SECURITY.md" in names
    assert "deploy/huggingface/README.md" in names
    assert "docs/huggingface-space-deployment.md" in names
    assert "reports/README.md" in names
    assert "reports/public/model_comparison.svg" in names
    assert "reports/public/woundscope-ui-showcase.webp" in names
    assert ".env" not in names
    assert "data/patient.png" not in names
    assert "docs/superpowers/notes.md" not in names
    assert all(len(entry["sha256"]) == 64 and entry["size"] > 0 for entry in manifest["files"])


def test_result_bundle_contains_only_safe_aggregate_artifacts(tmp_path: Path) -> None:
    bundles = _module()
    staging = tmp_path / "safe"
    (staging / "aggregate").mkdir(parents=True)
    (staging / "aggregate" / "verified_results.json").write_text(
        json.dumps({"status": "completed", "source_commit": "a" * 40}), encoding="utf-8"
    )
    (staging / "histories").mkdir()
    (staging / "histories" / "seed42.csv").write_text("epoch,dev_dice\n0,0.5\n", encoding="utf-8")
    (staging / "configs").mkdir()
    (staging / "configs" / "seed42.yaml").write_text("seed: 42\n", encoding="utf-8")
    output = tmp_path / "results.zip"

    manifest = bundles.build_result_bundle(staging, output, source_commit="a" * 40)
    verified = bundles.verify_bundle(
        output, expected_kind="results", expected_source_commit="a" * 40
    )

    assert verified == manifest
    assert {entry["path"] for entry in manifest["files"]} == {
        "aggregate/verified_results.json",
        "configs/seed42.yaml",
        "histories/seed42.csv",
    }


def test_result_bundle_accepts_https_source_url_without_treating_it_as_windows_path(
    tmp_path: Path,
) -> None:
    bundles = _module()
    staging = tmp_path / "safe"
    config = staging / "configs" / "seed42.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "source_repository: https://github.com/uwm-bigdata/wound-segmentation.git\n",
        encoding="utf-8",
    )

    manifest = bundles.build_result_bundle(
        staging, tmp_path / "results.zip", source_commit="a" * 40
    )

    assert [entry["path"] for entry in manifest["files"]] == ["configs/seed42.yaml"]


@pytest.mark.parametrize(
    "private_path",
    [
        "C:" + r"\Users\owner\private\artifact.json",
        r"\\server\share\private\artifact.json",
        r"\\?\UNC\server\share\private\artifact.json",
        "/content/drive/MyDrive/private/artifact.json",
    ],
)
def test_result_bundle_still_rejects_real_absolute_private_paths(
    tmp_path: Path, private_path: str
) -> None:
    bundles = _module()
    staging = tmp_path / "unsafe"
    config = staging / "configs" / "seed42.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"artifact: {private_path}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="absolute path"):
        bundles.build_result_bundle(staging, tmp_path / "results.zip", source_commit="a" * 40)


@pytest.mark.parametrize(
    "relative_path",
    [
        "models/best_model.safetensors",
        "exports/model.onnx",
        "private/sample_predictions.png",
        "metrics/per_image_metrics.csv",
        "tensorboard/events.out.tfevents.1",
    ],
)
def test_result_bundle_rejects_private_artifact_classes(tmp_path: Path, relative_path: str) -> None:
    bundles = _module()
    staging = tmp_path / "unsafe"
    path = staging / relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"private")

    with pytest.raises(ValueError, match=r"private|prohibited"):
        bundles.build_result_bundle(staging, tmp_path / "unsafe.zip", source_commit="a" * 40)


def test_bundle_verification_rejects_path_traversal(tmp_path: Path) -> None:
    bundles = _module()
    path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../escape.txt", "bad")
        archive.writestr(
            "bundle_manifest.json",
            json.dumps({"kind": "results", "source_commit": "a" * 40, "files": []}),
        )

    with pytest.raises(ValueError, match="unsafe archive path"):
        bundles.verify_bundle(path, expected_kind="results")
