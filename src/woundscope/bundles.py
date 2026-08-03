"""Deterministic source and result ZIP creation with privacy and checksum gates."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

SOURCE_ROOTS = (".github/", "app/", "configs/", "notebooks/", "scripts/", "src/", "tests/")
SOURCE_FILES = {
    ".env.example",
    ".gitignore",
    "CITATION.cff",
    "DATA_CARD.md",
    "Dockerfile",
    "LICENSE",
    "MODEL_CARD.md",
    "README.md",
    "pyproject.toml",
    "uv.lock",
}
SOURCE_SUFFIXES = {".cff", ".ipynb", ".lock", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
RESULT_SUFFIXES = {".csv", ".json", ".md", ".png", ".yaml", ".yml"}
PRIVATE_SUFFIXES = {".onnx", ".pt", ".pth", ".safetensors"}
SPACE_FILE_MAP = {
    "deploy/huggingface/README.md": "README.md",
    "Dockerfile": "Dockerfile",
    "LICENSE": "LICENSE",
    "pyproject.toml": "pyproject.toml",
    "uv.lock": "uv.lock",
}
SPACE_SOURCE_ROOTS = ("app/", "src/")
SPACE_SOURCE_SUFFIXES = {".py"}
SPACE_PROHIBITED_SUFFIXES = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".onnx",
    ".png",
    ".pt",
    ".pth",
    ".safetensors",
    ".tif",
    ".tiff",
    ".webp",
}
PRIVATE_TOKENS = {
    "checkpoint",
    "data_manifest",
    "error_gallery",
    "per_image",
    "sample_prediction",
    "sample_predictions",
    "tensorboard",
}
SECRET_PATTERN = re.compile(
    r"(?i)(authorization|client_secret|refresh_token|access_token|hf_token)\s*[:=]"
)
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9_])(?:[a-z]:[\\/]|/content/drive/|\\\\(?:\?\\UNC\\)?[^\\/\s]+[\\/])"
)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_archive_path(value: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise ValueError(f"unsafe archive path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe archive path: {value!r}")
    return path


def _git(repository: Path, *arguments: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
    )
    return completed.stdout


def _source_allowed(path: str) -> bool:
    if path in SOURCE_FILES:
        return True
    if not path.startswith(SOURCE_ROOTS):
        return False
    return PurePosixPath(path).suffix.casefold() in SOURCE_SUFFIXES


def _write_zip(output: Path, files: dict[str, bytes], manifest: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path, content in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
        manifest_content = json.dumps(
            manifest, indent=2, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        info = zipfile.ZipInfo("bundle_manifest.json", date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, manifest_content)
    temporary.replace(output)


def build_source_bundle(repository: str | Path, output: str | Path) -> dict[str, Any]:
    """Archive an explicit allowlist from committed HEAD, never working-tree bytes."""

    repository = Path(repository).resolve()
    output = Path(output).resolve()
    dirty = str(_git(repository, "status", "--porcelain", "--untracked-files=no")).strip()
    if dirty:
        raise RuntimeError("Tracked worktree must be clean before building a source bundle")
    source_commit = str(_git(repository, "rev-parse", "HEAD")).strip()
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise RuntimeError("Unable to resolve immutable source commit")

    listing = str(_git(repository, "ls-tree", "-r", "HEAD"))
    files: dict[str, bytes] = {}
    for line in listing.splitlines():
        metadata, path = line.split("\t", 1)
        mode, object_type, _object_sha = metadata.split(" ", 2)
        _safe_archive_path(path)
        if not _source_allowed(path):
            continue
        if object_type != "blob" or mode == "120000":
            raise ValueError(f"Source bundle does not permit non-regular files: {path}")
        files[path] = bytes(_git(repository, "show", f"HEAD:{path}", text=False))
    if not files:
        raise RuntimeError("Source allowlist selected no committed files")
    manifest = {
        "schema_version": 1,
        "kind": "source",
        "source_commit": source_commit,
        "files": [
            {"path": path, "size": len(content), "sha256": _sha256_bytes(content)}
            for path, content in sorted(files.items())
        ],
    }
    _write_zip(output, files, manifest)
    verify_bundle(output, expected_kind="source", expected_source_commit=source_commit)
    return manifest


def _validate_result_member(path: str, content: bytes) -> None:
    normalized = path.casefold()
    pure = _safe_archive_path(path)
    if pure.suffix.casefold() in PRIVATE_SUFFIXES or any(
        token in normalized for token in PRIVATE_TOKENS
    ):
        raise ValueError(f"private or prohibited result artifact: {path}")
    if pure.suffix.casefold() not in RESULT_SUFFIXES:
        raise ValueError(f"private or prohibited result artifact type: {path}")
    if pure.suffix.casefold() == ".png" and pure.parts[0] != "public_charts":
        raise ValueError(f"private or prohibited image artifact: {path}")
    if pure.suffix.casefold() != ".png":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"Safe result text artifact is not UTF-8: {path}") from exc
        if SECRET_PATTERN.search(text):
            raise ValueError(f"private or prohibited secret-like content: {path}")
        if ABSOLUTE_PATH_PATTERN.search(text):
            raise ValueError(f"private or prohibited absolute path: {path}")


def _validate_space_member(path: str, content: bytes) -> None:
    pure = _safe_archive_path(path)
    if pure.name.casefold() == ".env" or pure.suffix.casefold() in SPACE_PROHIBITED_SUFFIXES:
        raise ValueError(f"prohibited Space member: {path}")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Space member is not UTF-8: {path}") from exc
    if SECRET_PATTERN.search(text):
        raise ValueError(f"secret-like Space member content: {path}")
    if ABSOLUTE_PATH_PATTERN.search(_space_text_for_path_scan(path, text)):
        raise ValueError(f"absolute path in Space member content: {path}")


def _space_text_for_path_scan(path: str, text: str) -> str:
    if path != "src/woundscope/bundles.py":
        return text
    try:
        module = ast.parse(text)
    except SyntaxError:
        return text
    for statement in module.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        value = statement.value
        if not (
            isinstance(target, ast.Name)
            and target.id == "ABSOLUTE_PATH_PATTERN"
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "re"
            and value.func.attr == "compile"
            and len(value.args) == 1
            and not value.keywords
        ):
            continue
        argument = value.args[0]
        try:
            pattern = ast.literal_eval(argument)
        except ValueError:
            continue
        if pattern != ABSOLUTE_PATH_PATTERN.pattern:
            continue
        if argument.end_lineno is None or argument.end_col_offset is None:
            continue
        encoded = text.encode("utf-8")
        lines = encoded.splitlines(keepends=True)
        start = sum(len(line) for line in lines[: argument.lineno - 1]) + argument.col_offset
        end = sum(len(line) for line in lines[: argument.end_lineno - 1]) + argument.end_col_offset
        masked = bytes(byte if byte in b"\r\n" else ord(" ") for byte in encoded[start:end])
        return (encoded[:start] + masked + encoded[end:]).decode("utf-8")
    return text


def _space_destination(source_path: str) -> str | None:
    mapped = SPACE_FILE_MAP.get(source_path)
    if mapped is not None:
        return mapped
    if source_path.startswith(SPACE_SOURCE_ROOTS):
        return source_path
    return None


def _validate_space_manifest(manifest: dict[str, Any]) -> None:
    records = manifest.get("files")
    if not isinstance(records, list):
        raise ValueError("Space bundle file inventory is invalid")
    source_paths: set[str] = set()
    destination_paths: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Space bundle file inventory is invalid")
        path = str(record.get("path", ""))
        source_path = str(record.get("source_path", ""))
        _safe_archive_path(path)
        _safe_archive_path(source_path)
        if _space_destination(source_path) != path:
            raise ValueError(f"Space bundle source mapping is invalid: {source_path}")
        if source_path.startswith(SPACE_SOURCE_ROOTS) and (
            PurePosixPath(source_path).suffix.casefold() not in SPACE_SOURCE_SUFFIXES
        ):
            raise ValueError(f"Space bundle source mapping is invalid: {source_path}")
        if source_path in source_paths or path in destination_paths:
            raise ValueError("Space bundle file inventory contains duplicate paths")
        source_paths.add(source_path)
        destination_paths.add(path)
    if set(SPACE_FILE_MAP).difference(source_paths):
        raise ValueError("Space bundle is missing required mapped files")


def _read_head_space_files(repository: Path) -> tuple[str, dict[str, bytes], dict[str, str]]:
    dirty = str(_git(repository, "status", "--porcelain", "--untracked-files=no")).strip()
    if dirty:
        raise RuntimeError("Tracked worktree must be clean before building a Space bundle")
    source_commit = str(_git(repository, "rev-parse", "HEAD")).strip()
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise RuntimeError("Unable to resolve immutable source commit")

    listing = str(_git(repository, "ls-tree", "-r", "-z", source_commit))
    selected: list[str] = []
    for line in listing.split("\0"):
        if not line:
            continue
        metadata, source_path = line.split("\t", 1)
        mode, object_type, _object_sha = metadata.split(" ", 2)
        _safe_archive_path(source_path)
        destination = _space_destination(source_path)
        if destination is None:
            continue
        if object_type != "blob" or mode == "120000":
            raise ValueError(f"Space bundle does not permit non-regular files: {source_path}")
        if source_path.startswith(SPACE_SOURCE_ROOTS):
            pure = PurePosixPath(source_path)
            if (
                pure.name.casefold() == ".env"
                or pure.suffix.casefold() in SPACE_PROHIBITED_SUFFIXES
            ):
                raise ValueError(f"prohibited Space member: {source_path}")
            if pure.suffix.casefold() not in SPACE_SOURCE_SUFFIXES:
                raise ValueError(f"unexpected Space member: {source_path}")
        selected.append(source_path)

    missing = set(SPACE_FILE_MAP).difference(selected)
    if missing:
        raise ValueError(f"Space bundle is missing required mapped files: {sorted(missing)!r}")
    files: dict[str, bytes] = {}
    source_paths: dict[str, str] = {}
    for source_path in sorted(selected):
        destination = _space_destination(source_path)
        if destination is None:
            raise RuntimeError("Space source mapping was unexpectedly absent")
        content = bytes(_git(repository, "show", f"{source_commit}:{source_path}", text=False))
        _validate_space_member(destination, content)
        if destination in files:
            raise ValueError(f"Space bundle destination collision: {destination}")
        files[destination] = content
        source_paths[destination] = source_path
    return source_commit, files, source_paths


def build_huggingface_space_bundle(
    repository: str | Path,
    output_directory: str | Path,
    output_zip: str | Path,
) -> dict[str, Any]:
    """Build and verify a code-only Space candidate from committed HEAD."""

    repository = Path(repository).resolve()
    output_directory = Path(output_directory).resolve()
    output_zip = Path(output_zip).resolve()
    if output_zip.is_relative_to(output_directory):
        raise ValueError("Space bundle ZIP cannot be inside the candidate directory")
    if output_directory.exists() and (
        not output_directory.is_dir() or any(output_directory.iterdir())
    ):
        raise ValueError("Space candidate output directory must be empty")
    if output_zip.exists():
        raise ValueError("Space bundle output ZIP must not already exist")

    source_commit, files, source_paths = _read_head_space_files(repository)
    manifest = {
        "schema_version": 1,
        "kind": "huggingface_space",
        "source_commit": source_commit,
        "files": [
            {
                "path": path,
                "source_path": source_paths[path],
                "size": len(content),
                "sha256": _sha256_bytes(content),
            }
            for path, content in sorted(files.items())
        ],
    }
    _validate_space_manifest(manifest)
    manifest_content = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode(
        "utf-8"
    )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(
            prefix=".woundscope-space-", dir=output_directory.parent
        ) as directory_temp,
        tempfile.TemporaryDirectory(prefix=".woundscope-space-", dir=output_zip.parent) as zip_temp,
    ):
        staged_directory = Path(directory_temp) / "candidate"
        staged_directory.mkdir()
        for path, content in files.items():
            destination = staged_directory / Path(*PurePosixPath(path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        (staged_directory / "bundle_manifest.json").write_bytes(manifest_content)
        staged_zip = Path(zip_temp) / output_zip.name
        _write_zip(staged_zip, files, manifest)
        verify_huggingface_space_candidate(
            staged_directory,
            staged_zip,
            expected_source_commit=source_commit,
        )

        output_directory_existed = output_directory.exists()
        candidate_published = False
        if output_directory_existed:
            output_directory.rmdir()
        try:
            staged_directory.replace(output_directory)
            candidate_published = True
            staged_zip.replace(output_zip)
        except OSError:
            if candidate_published:
                shutil.rmtree(output_directory)
            if output_directory_existed:
                output_directory.mkdir()
            raise
    return manifest


def verify_huggingface_space_candidate(
    directory: str | Path,
    bundle: str | Path,
    *,
    expected_source_commit: str | None = None,
) -> dict[str, Any]:
    """Verify a Space candidate tree exactly matches its verified bundle."""

    manifest = verify_bundle(
        bundle,
        expected_kind="huggingface_space",
        expected_source_commit=expected_source_commit,
    )
    _validate_space_manifest(manifest)
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ValueError("Space candidate directory is missing")
    expected_names = {"bundle_manifest.json", *[record["path"] for record in manifest["files"]]}
    actual_names: set[str] = set()
    for member in directory.rglob("*"):
        if member.is_symlink():
            raise ValueError(f"Space candidate does not permit symlinks: {member}")
        if member.is_file():
            relative = member.relative_to(directory).as_posix()
            _safe_archive_path(relative)
            actual_names.add(relative)
    if actual_names != expected_names:
        raise ValueError("Space candidate inventory does not match bundle")
    with zipfile.ZipFile(bundle) as archive:
        for name in sorted(expected_names):
            candidate_content = (directory / Path(*PurePosixPath(name).parts)).read_bytes()
            bundle_content = archive.read(name)
            if candidate_content != bundle_content:
                raise ValueError(f"Space candidate checksum mismatch: {name}")
        for record in manifest["files"]:
            _validate_space_member(str(record["path"]), archive.read(record["path"]))
    return manifest


def build_result_bundle(
    staging_root: str | Path,
    output: str | Path,
    *,
    source_commit: str,
) -> dict[str, Any]:
    """Archive an already-curated aggregate staging tree after enforcing privacy rules."""

    staging_root = Path(staging_root).resolve()
    output = Path(output).resolve()
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("source_commit must be a lowercase 40-character Git SHA")
    files: dict[str, bytes] = {}
    for path in sorted(staging_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(staging_root).as_posix()
        content = path.read_bytes()
        _validate_result_member(relative, content)
        files[relative] = content
    if not files:
        raise ValueError("Safe result staging tree is empty")
    manifest = {
        "schema_version": 1,
        "kind": "results",
        "source_commit": source_commit,
        "files": [
            {"path": path, "size": len(content), "sha256": _sha256_bytes(content)}
            for path, content in sorted(files.items())
        ],
    }
    _write_zip(output, files, manifest)
    verify_bundle(output, expected_kind="results", expected_source_commit=source_commit)
    return manifest


def verify_bundle(
    bundle: str | Path,
    *,
    expected_kind: str,
    expected_source_commit: str | None = None,
) -> dict[str, Any]:
    """Verify path safety, exact inventory, sizes, hashes, kind, commit, and privacy."""

    bundle = Path(bundle)
    with zipfile.ZipFile(bundle) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        for name in names:
            _safe_archive_path(name)
        if len(names) != len(set(names)):
            raise ValueError("Bundle contains duplicate archive paths")
        if "bundle_manifest.json" not in names:
            raise ValueError("Bundle manifest is missing")
        manifest = json.loads(archive.read("bundle_manifest.json"))
        if manifest.get("schema_version") != 1 or manifest.get("kind") != expected_kind:
            raise ValueError("Bundle kind or schema is incompatible")
        source_commit = str(manifest.get("source_commit", ""))
        if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
            raise ValueError("Bundle source commit is invalid")
        if expected_source_commit is not None and source_commit != expected_source_commit:
            raise ValueError("Bundle source commit does not match expected commit")
        records = manifest.get("files")
        if not isinstance(records, list):
            raise ValueError("Bundle file inventory is invalid")
        expected_names = {"bundle_manifest.json"}
        for record in records:
            path = str(record.get("path", ""))
            _safe_archive_path(path)
            expected_names.add(path)
            try:
                content = archive.read(path)
            except KeyError as exc:
                raise ValueError(f"Bundle inventory member is missing: {path}") from exc
            if len(content) != record.get("size") or _sha256_bytes(content) != record.get("sha256"):
                raise ValueError(f"Bundle checksum mismatch: {path}")
            if expected_kind == "results":
                _validate_result_member(path, content)
        if set(names) != expected_names:
            raise ValueError("Bundle contains unlisted or duplicate members")
    return manifest


def extract_bundle(
    bundle: str | Path,
    destination: str | Path,
    *,
    expected_kind: str,
    expected_source_commit: str | None = None,
) -> dict[str, Any]:
    """Verify first, then extract every inventoried member into an empty directory."""

    manifest = verify_bundle(
        bundle,
        expected_kind=expected_kind,
        expected_source_commit=expected_source_commit,
    )
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Bundle extraction destination must be empty")
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as archive:
        for name in ["bundle_manifest.json", *[record["path"] for record in manifest["files"]]]:
            relative = _safe_archive_path(str(name))
            target = (destination / Path(*relative.parts)).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"unsafe archive path: {name!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(str(name)))
    return manifest
