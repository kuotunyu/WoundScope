from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

from woundscope import bundles


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


def _commit_all(repository: Path, message: str) -> None:
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _space_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    files = {
        "deploy/huggingface/README.md": "---\nsdk: docker\napp_port: 7860\n---\nPERMISSION_PENDING\n",
        "Dockerfile": "FROM python:3.11-slim\n",
        "LICENSE": "Apache License 2.0\n",
        "pyproject.toml": "[project]\nname='woundscope'\nversion='0.1.0'\n",
        "uv.lock": "version = 1\n",
        "app/app.py": "from woundscope import __version__\n",
        "src/woundscope/__init__.py": '__version__ = "0.1.0"\n',
    }
    for relative, content in files.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "Test")
    _git(repository, "config", "user.email", "test@example.com")
    _commit_all(repository, "fixture")
    return repository


def test_space_bundle_uses_committed_allowlist_and_is_deterministic(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_zip = tmp_path / "first.zip"
    second_zip = tmp_path / "second.zip"

    first = bundles.build_huggingface_space_bundle(repository, first_dir, first_zip)
    second = bundles.build_huggingface_space_bundle(repository, second_dir, second_zip)

    assert first == second
    assert _sha256(first_zip) == _sha256(second_zip)
    assert first["kind"] == "huggingface_space"
    assert (first_dir / "README.md").read_text(encoding="utf-8").startswith("---\n")
    assert not (first_dir / "deploy").exists()
    assert {record["path"] for record in first["files"]} == {
        "Dockerfile",
        "LICENSE",
        "README.md",
        "app/app.py",
        "pyproject.toml",
        "src/woundscope/__init__.py",
        "uv.lock",
    }
    assert (
        bundles.verify_huggingface_space_candidate(
            first_dir, first_zip, expected_source_commit=first["source_commit"]
        )
        == first
    )


@pytest.mark.parametrize(
    ("relative_path", "content", "message"),
    [
        ("app/model.onnx", b"weights", "prohibited"),
        ("src/woundscope/patient.png", b"image", "prohibited"),
        ("app/.env", b"HF_TOKEN=secret", "prohibited"),
        ("app/private.py", b"HF_TOKEN = 'secret'\n", "secret-like"),
        ("app/path.py", b"ROOT = 'C:\\\\Users\\\\owner\\\\private'\n", "absolute path"),
        ("app/unexpected.txt", b"unexpected", "unexpected"),
    ],
)
def test_space_bundle_rejects_prohibited_committed_members(
    tmp_path: Path, relative_path: str, content: bytes, message: str
) -> None:
    repository = _space_repository(tmp_path)
    path = repository / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    _commit_all(repository, "unsafe fixture")

    with pytest.raises(ValueError, match=message):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )
    assert not (tmp_path / "candidate").exists()
    assert not (tmp_path / "candidate.zip").exists()


def test_space_bundle_rejects_allowlisted_symlink(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    blob = (
        subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repository,
            check=True,
            capture_output=True,
            input=b"app.py",
        )
        .stdout.decode("ascii")
        .strip()
    )
    _git(repository, "update-index", "--add", "--cacheinfo", f"120000,{blob},app/linked.py")
    _git(repository, "commit", "-m", "symlink fixture")
    _git(repository, "checkout", "-f")

    with pytest.raises(ValueError, match="non-regular"):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )


def test_space_bundle_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "existing.txt").write_text("preserve", encoding="utf-8")

    with pytest.raises(ValueError, match="must be empty"):
        bundles.build_huggingface_space_bundle(repository, candidate, tmp_path / "candidate.zip")

    assert (candidate / "existing.txt").read_text(encoding="utf-8") == "preserve"


def test_space_bundle_rejects_zip_inside_candidate_directory(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    candidate = tmp_path / "candidate"

    with pytest.raises(ValueError, match="inside"):
        bundles.build_huggingface_space_bundle(repository, candidate, candidate / "candidate.zip")

    assert not candidate.exists()


def test_space_bundle_requires_clean_tracked_worktree(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    (repository / "Dockerfile").write_text("FROM changed\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Tracked worktree must be clean"):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )


def test_space_bundle_allows_trusted_absolute_path_detector_definition(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    detector = repository / "src" / "woundscope" / "bundles.py"
    detector.write_text(
        "import re\n"
        f"ABSOLUTE_PATH_PATTERN = re.compile({bundles.ABSOLUTE_PATH_PATTERN.pattern!r})\n",
        encoding="utf-8",
    )
    _commit_all(repository, "add path detector")

    manifest = bundles.build_huggingface_space_bundle(
        repository, tmp_path / "candidate", tmp_path / "candidate.zip"
    )

    assert "src/woundscope/bundles.py" in {record["path"] for record in manifest["files"]}


def test_space_bundle_rejects_private_path_in_unrelated_compiled_pattern(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    private_pattern = repository / "src" / "woundscope" / "private_pattern.py"
    private_pattern.write_text(
        'import re\nPRIVATE_PATH_PATTERN = re.compile(r"C:\\\\Users\\\\owner\\\\private")\n',
        encoding="utf-8",
    )
    _commit_all(repository, "add private pattern")

    with pytest.raises(ValueError, match="absolute path"):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )


def test_space_bundle_rejects_private_path_in_untrusted_detector_identifier(
    tmp_path: Path,
) -> None:
    repository = _space_repository(tmp_path)
    private_pattern = repository / "src" / "woundscope" / "private_pattern.py"
    private_pattern.write_text(
        'import re\nABSOLUTE_PATH_PATTERN = re.compile(r"C:\\\\Users\\\\owner\\\\private")\n',
        encoding="utf-8",
    )
    _commit_all(repository, "reuse detector identifier")

    with pytest.raises(ValueError, match="absolute path"):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )


def test_space_bundle_reads_tree_and_blobs_from_resolved_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _space_repository(tmp_path)
    original_app = (repository / "app" / "app.py").read_text(encoding="utf-8")
    source_commit = _git(repository, "rev-parse", "HEAD")
    original_git = bundles._git
    advanced = False

    def advancing_git(repository_path: Path, *arguments: str, text: bool = True) -> str | bytes:
        nonlocal advanced
        result = original_git(repository_path, *arguments, text=text)
        if arguments == ("rev-parse", "HEAD") and not advanced:
            advanced = True
            (repository / "app" / "app.py").write_text("moved HEAD\n", encoding="utf-8")
            _commit_all(repository, "move HEAD")
        return result

    monkeypatch.setattr(bundles, "_git", advancing_git)
    candidate = tmp_path / "candidate"
    manifest = bundles.build_huggingface_space_bundle(
        repository, candidate, tmp_path / "candidate.zip"
    )

    assert manifest["source_commit"] == source_commit
    assert (candidate / "app" / "app.py").read_text(encoding="utf-8") == original_app


def test_space_bundle_restores_caller_empty_directory_when_zip_publish_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _space_repository(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    bundle = tmp_path / "candidate.zip"
    original_replace = Path.replace

    def fail_zip_publish(path: Path, target: str | Path) -> Path:
        if Path(target).resolve() == bundle.resolve():
            raise OSError("simulated ZIP publish failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_zip_publish)

    with pytest.raises(OSError, match="simulated ZIP publish failure"):
        bundles.build_huggingface_space_bundle(repository, candidate, bundle)

    assert candidate.is_dir()
    assert list(candidate.iterdir()) == []


def test_space_candidate_verifier_rejects_tampered_candidate_member(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    candidate = tmp_path / "candidate"
    bundle = tmp_path / "candidate.zip"
    manifest = bundles.build_huggingface_space_bundle(repository, candidate, bundle)
    (candidate / "app" / "app.py").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="candidate checksum mismatch"):
        bundles.verify_huggingface_space_candidate(
            candidate, bundle, expected_source_commit=manifest["source_commit"]
        )


def test_space_candidate_verifier_rejects_tampered_zip_member(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    candidate = tmp_path / "candidate"
    bundle = tmp_path / "candidate.zip"
    manifest = bundles.build_huggingface_space_bundle(repository, candidate, bundle)
    replacement = tmp_path / "replacement.zip"
    with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(replacement, "w") as target:
        for name in source.namelist():
            content = source.read(name)
            target.writestr(name, b"tampered\n" if name == "app/app.py" else content)
    replacement.replace(bundle)

    with pytest.raises(ValueError, match="checksum mismatch"):
        bundles.verify_huggingface_space_candidate(
            candidate, bundle, expected_source_commit=manifest["source_commit"]
        )
