"""Deterministic source and result ZIP creation with privacy and checksum gates."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
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
ABSOLUTE_PATH_PATTERN = re.compile(r"(?i)(?:[a-z]:[\\/]|/content/drive/)")


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
            raise ValueError(f"private or prohibited absolute Drive path: {path}")


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
