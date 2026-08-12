from __future__ import annotations

import hashlib
import importlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI

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
        ".dockerignore": "__pycache__\n",
        "deploy/huggingface/README.md": "---\nsdk: docker\napp_port: 7860\n---\nPERMISSION_PENDING\n",
        "Dockerfile": "FROM python:3.11-slim\n",
        "LICENSE": "Apache License 2.0\n",
        "pyproject.toml": "[project]\nname='woundscope'\nversion='0.1.0'\n",
        "uv.lock": "version = 1\n",
        "app/app.py": "from woundscope import __version__\n",
        "frontend/package.json": '{"name":"woundscope-ui"}\n',
        "frontend/pnpm-lock.yaml": "lockfileVersion: '9.0'\n",
        "frontend/pnpm-workspace.yaml": "allowBuilds: {}\n",
        "frontend/index.html": "<div id='root'></div>\n",
        "frontend/tsconfig.app.json": "{}\n",
        "frontend/tsconfig.json": "{}\n",
        "frontend/tsconfig.node.json": "{}\n",
        "frontend/vite.config.ts": "export default {};\n",
        "frontend/src/main.tsx": "export {};\n",
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
        ".dockerignore",
        "Dockerfile",
        "LICENSE",
        "README.md",
        "app/app.py",
        "frontend/index.html",
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "frontend/pnpm-workspace.yaml",
        "frontend/src/main.tsx",
        "frontend/tsconfig.app.json",
        "frontend/tsconfig.json",
        "frontend/tsconfig.node.json",
        "frontend/vite.config.ts",
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


def test_primary_entrypoint_exposes_fastapi_without_importing_gradio() -> None:
    module = importlib.import_module("app.app")

    assert isinstance(module.app, FastAPI)
    assert "demo" not in vars(module)


def test_task_5_import_smoke_preserves_verified_candidate_inventory(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    module = repository / "src" / "woundscope" / "gradio_app.py"
    module.write_text(
        "class Demo:\n"
        "    analytics_enabled = False\n"
        "    delete_cache = (600, 600)\n\n"
        "def build_demo():\n"
        "    return Demo()\n",
        encoding="utf-8",
    )
    _commit_all(repository, "add import smoke fixture")

    def run_import(candidate: Path, *, no_bytecode: bool) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        environment.pop("PYTHONPYCACHEPREFIX", None)
        environment["PYTHONPATH"] = str(candidate / "src")
        command = [sys.executable]
        if no_bytecode:
            command.append("-B")
        command.extend(
            [
                "-c",
                "from woundscope.gradio_app import build_demo; "
                "demo=build_demo(); "
                "assert demo.analytics_enabled is False; "
                "assert demo.delete_cache==(600,600); "
                "print('HF_SPACE_IMPORT_SMOKE_PASS')",
            ]
        )
        return subprocess.run(
            command,
            cwd=candidate,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
        )

    unsafe_candidate = tmp_path / "unsafe-candidate"
    unsafe_bundle = tmp_path / "unsafe-candidate.zip"
    unsafe_manifest = bundles.build_huggingface_space_bundle(
        repository, unsafe_candidate, unsafe_bundle
    )
    assert (
        bundles.verify_huggingface_space_candidate(
            unsafe_candidate,
            unsafe_bundle,
            expected_source_commit=unsafe_manifest["source_commit"],
        )
        == unsafe_manifest
    )

    unsafe_result = run_import(unsafe_candidate, no_bytecode=False)

    assert "HF_SPACE_IMPORT_SMOKE_PASS" in unsafe_result.stdout
    with pytest.raises(ValueError, match="inventory does not match bundle"):
        bundles.verify_huggingface_space_candidate(
            unsafe_candidate,
            unsafe_bundle,
            expected_source_commit=unsafe_manifest["source_commit"],
        )

    guide = Path("docs/huggingface-space-deployment.md").read_text(encoding="utf-8")
    smoke_command = next(
        line for line in guide.splitlines() if "HF_SPACE_IMPORT_SMOKE_PASS" in line
    )
    prescribed_no_bytecode = ".venv\\Scripts\\python.exe -B -c" in smoke_command
    safe_candidate = tmp_path / "safe-candidate"
    safe_bundle = tmp_path / "safe-candidate.zip"
    safe_manifest = bundles.build_huggingface_space_bundle(repository, safe_candidate, safe_bundle)

    safe_result = run_import(safe_candidate, no_bytecode=prescribed_no_bytecode)

    assert "HF_SPACE_IMPORT_SMOKE_PASS" in safe_result.stdout
    assert (
        bundles.verify_huggingface_space_candidate(
            safe_candidate,
            safe_bundle,
            expected_source_commit=safe_manifest["source_commit"],
        )
        == safe_manifest
    )
    smoke_position = guide.index("HF_SPACE_IMPORT_SMOKE_PASS")
    docker_position = guide.index("docker build", smoke_position)
    verify_after_import = guide.index("HF_SPACE_POST_IMPORT_VERIFY_PASS", smoke_position)
    verify_after_docker = guide.index("HF_SPACE_POST_DOCKER_VERIFY_PASS", docker_position)
    assert smoke_position < verify_after_import < docker_position < verify_after_docker


def test_space_bundle_allows_checkpoint_named_python_modules(tmp_path: Path) -> None:
    repository = _space_repository(tmp_path)
    module = repository / "src" / "woundscope" / "checkpointing.py"
    module.write_text("def file_sha256():\n    return 'source helper'\n", encoding="utf-8")
    _commit_all(repository, "add checkpoint helper")

    manifest = bundles.build_huggingface_space_bundle(
        repository, tmp_path / "candidate", tmp_path / "candidate.zip"
    )

    assert "src/woundscope/checkpointing.py" in {record["path"] for record in manifest["files"]}


@pytest.mark.parametrize(
    ("relative_path", "content", "message"),
    [
        ("app/model.onnx", b"weights", "prohibited"),
        ("src/woundscope/patient.png", b"image", "prohibited"),
        ("app/.env", b"HF_TOKEN=secret", "prohibited"),
        ("app/.env.private.py", b"VALUE = 1\n", "prohibited"),
        ("src/woundscope/checkpoints/loader.py", b"VALUE = 1\n", "prohibited"),
        ("app/GALLERY/viewer.py", b"VALUE = 1\n", "prohibited"),
        ("app/sample_predictions/render.py", b"VALUE = 1\n", "prohibited"),
        ("src/woundscope/tensorboard/plugin.py", b"VALUE = 1\n", "prohibited"),
        ("app/artifacts/build.py", b"VALUE = 1\n", "prohibited"),
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


def test_space_bundle_rejects_private_path_comment_in_trusted_detector_assignment(
    tmp_path: Path,
) -> None:
    repository = _space_repository(tmp_path)
    detector = repository / "src" / "woundscope" / "bundles.py"
    detector.write_text(
        "import re\n"
        "ABSOLUTE_PATH_PATTERN = re.compile(\n"
        f"    {bundles.ABSOLUTE_PATH_PATTERN.pattern!r}"
        "  # C:\\Users\\owner\\private\n"
        ")\n",
        encoding="utf-8",
    )
    _commit_all(repository, "add private path beside detector literal")

    with pytest.raises(ValueError, match="absolute path"):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )


def test_space_bundle_rejects_private_path_comment_between_adjacent_trusted_literals(
    tmp_path: Path,
) -> None:
    repository = _space_repository(tmp_path)
    detector = repository / "src" / "woundscope" / "bundles.py"
    pattern = bundles.ABSOLUTE_PATH_PATTERN.pattern
    split = len(pattern) // 2
    detector.write_text(
        "import re\n"
        "ABSOLUTE_PATH_PATTERN = re.compile(\n"
        f"    {pattern[:split]!r}\n"
        "    # C:\\Users\\owner\\private\n"
        f"    {pattern[split:]!r}\n"
        ")\n",
        encoding="utf-8",
    )
    _commit_all(repository, "split detector around private path comment")

    with pytest.raises(ValueError, match="absolute path"):
        bundles.build_huggingface_space_bundle(
            repository, tmp_path / "candidate", tmp_path / "candidate.zip"
        )


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
