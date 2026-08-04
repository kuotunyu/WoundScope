from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPOSITORY_ROOT / "scripts" / "audit_repository_privacy.py"


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _run_audit(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), "--repository", str(repository)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _tracked_repository(tmp_path: Path, relative_path: str, content: bytes) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    target = repository / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    _git(repository, "add", "--force", "--", relative_path)
    return repository


@pytest.mark.parametrize(
    ("relative_path", "expected_rule"),
    [
        (".env.production", "environment_file"),
        ("configs/.env.example", "environment_file"),
        ("models/model.pth", "model_artifact"),
        ("checkpoints/model.ckpt", "private_artifact_directory"),
        ("reports/private/patient.png", "raster_image"),
        ("logs/events.out.tfevents.1", "tensorboard_event"),
        ("data_manifest.csv", "image_level_manifest"),
        ("metrics/per_image_metrics.csv", "image_level_artifact"),
        ("sample_ids.csv", "image_level_artifact"),
        ("manifest.csv", "image_level_manifest"),
        ("reports/aggregate_metrics.csv", "tabular_data_artifact"),
        ("artifacts/result.json", "private_artifact_directory"),
    ],
)
def test_audit_rejects_force_tracked_private_artifacts(
    tmp_path: Path,
    relative_path: str,
    expected_rule: str,
) -> None:
    repository = _tracked_repository(tmp_path, relative_path, b"synthetic fixture\n")

    completed = _run_audit(repository)

    assert completed.returncode == 1, completed.stderr
    report = json.loads(completed.stdout)
    assert report["status"] == "failed"
    assert report["violations"] == [{"path": relative_path, "rule": expected_rule}]


def test_audit_allows_public_source_and_aggregate_assets(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    safe_files = {
        ".env.example": b"HF_TOKEN=\n",
        "data/README.md": b"Download instructions only.\n",
        "docs/token-example.txt": b"HF_TOKEN=secret\nGITHUB_TOKEN=${GITHUB_TOKEN}\n",
        "reports/public/model_comparison.svg": b"<svg></svg>\n",
        "src/woundscope/example.py": b"VALUE = 1\n",
    }
    for relative_path, content in safe_files.items():
        target = repository / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    _git(repository, "add", "--force", "--", *safe_files)

    completed = _run_audit(repository)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "status": "ok",
        "tracked_files": 5,
        "violations": [],
    }


def test_audit_rejects_local_home_paths_without_echoing_content(tmp_path: Path) -> None:
    local_path = "C:" + "\\Users\\example\\private\\artifact.json"
    repository = _tracked_repository(
        tmp_path,
        "docs/notes.md",
        f"public line\nlocal evidence: {local_path}\n".encode(),
    )

    completed = _run_audit(repository)

    assert completed.returncode == 1, completed.stderr
    report = json.loads(completed.stdout)
    assert report["violations"] == [{"line": 2, "path": "docs/notes.md", "rule": "local_home_path"}]
    assert local_path not in completed.stdout


def test_audit_reads_the_staged_blob_instead_of_the_worktree(tmp_path: Path) -> None:
    local_path = "C:" + "\\Users\\example\\private\\artifact.json"
    repository = _tracked_repository(
        tmp_path,
        "docs/notes.md",
        f"staged evidence: {local_path}\n".encode(),
    )
    (repository / "docs/notes.md").write_text("safe worktree replacement\n", encoding="utf-8")

    completed = _run_audit(repository)

    assert completed.returncode == 1, completed.stderr
    report = json.loads(completed.stdout)
    assert report["violations"] == [{"line": 1, "path": "docs/notes.md", "rule": "local_home_path"}]
    assert local_path not in completed.stdout


def test_audit_rejects_a_git_symlink_without_following_it(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    object_id = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repository,
            check=True,
            input=b"docs/public-target.md\n",
            capture_output=True,
        )
        .stdout.decode("ascii")
        .strip()
    )
    _git(
        repository,
        "update-index",
        "--add",
        "--cacheinfo",
        f"120000,{object_id},docs/external-link",
    )

    completed = _run_audit(repository)

    assert completed.returncode == 1, completed.stderr
    assert json.loads(completed.stdout)["violations"] == [
        {"path": "docs/external-link", "rule": "non_regular_file"}
    ]


def test_audit_rejects_high_confidence_secrets_without_echoing_them(tmp_path: Path) -> None:
    token = "hf_" + "A" * 32
    repository = _tracked_repository(
        tmp_path,
        "docs/configuration.txt",
        f"HF_TOKEN={token}\n".encode(),
    )

    completed = _run_audit(repository)

    assert completed.returncode == 1, completed.stderr
    assert json.loads(completed.stdout)["violations"] == [
        {"line": 1, "path": "docs/configuration.txt", "rule": "secret_content"}
    ]
    assert token not in completed.stdout
