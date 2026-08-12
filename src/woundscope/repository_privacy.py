"""Repository-level privacy audit shared by local, CI, and release gates."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

ALLOWED_DATA_FILES = {"data/.gitkeep", "data/readme.md"}
ALLOWED_RASTER_FILES = {"reports/public/woundscope-ui-showcase.webp"}
PRIVATE_DIRECTORY_COMPONENTS = {
    "artifact",
    "artifacts",
    "checkpoint",
    "checkpoints",
    "error_gallery",
    "galleries",
    "gallery",
    "generated",
    "lightning_logs",
    "predictions",
    "private",
    "runs",
    "sample_prediction",
    "sample_predictions",
    "tensorboard",
    "wandb",
}
MODEL_ARTIFACT_SUFFIXES = {
    ".bin",
    ".ckpt",
    ".h5",
    ".hdf5",
    ".joblib",
    ".keras",
    ".npy",
    ".npz",
    ".onnx",
    ".pb",
    ".pkl",
    ".pt",
    ".pth",
    ".safetensors",
    ".tflite",
}
RASTER_IMAGE_SUFFIXES = {
    ".bmp",
    ".dcm",
    ".dicom",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
TABULAR_DATA_SUFFIXES = {
    ".arrow",
    ".csv",
    ".feather",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".tsv",
}
IMAGE_LEVEL_NAME_FRAGMENTS = {
    "image-level",
    "image_level",
    "patient-id",
    "patient_id",
    "per-image",
    "per_image",
    "sample-id",
    "sample_id",
    "sample-prediction",
    "sample_prediction",
}
LOCAL_HOME_PATTERN = re.compile(
    r"(?i)(?:[a-z]:[\\/](?:users)[\\/][^\\/\s`\"'<>]+|"
    r"(?<![a-z0-9:])/(?:home|users)/[^/\s`\"'<>]+)"
)
DIRECT_SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])hf_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])gh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])"),
    re.compile(r"(?<![A-Za-z0-9])AIza[A-Za-z0-9_-]{30,}"),
    re.compile(r"(?<![A-Za-z0-9])sk_live_[A-Za-z0-9]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:authorization|client_secret|refresh_token|access_token|hf_token|"
    r"github_token|api_key|secret_key)\b\s*[:=]\s*[\"']?([^\s\"'#,;]+)"
)
SECRET_PLACEHOLDERS = {
    "changeme",
    "change_me",
    "dummy",
    "example",
    "none",
    "null",
    "replace_me",
    "secret",
    "synthetic",
    "test",
    "token",
    "your_token",
}


REGULAR_FILE_MODES = {"100644", "100755"}


def _tracked_entries(repository: Path) -> list[tuple[str, str, str, str]]:
    completed = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    entries: list[tuple[str, str, str, str]] = []
    for raw_entry in completed.stdout.decode("utf-8").split("\0"):
        if not raw_entry:
            continue
        metadata, path = raw_entry.split("\t", 1)
        mode, object_id, stage = metadata.split(" ")
        entries.append((path, mode, object_id, stage))
    return sorted(entries)


def _read_index_blob(repository: Path, object_id: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", object_id],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def _contains_high_confidence_secret(line: str) -> bool:
    if any(pattern.search(line) for pattern in DIRECT_SECRET_PATTERNS):
        return True
    for match in SECRET_ASSIGNMENT_PATTERN.finditer(line):
        value = match.group(1).strip().casefold()
        if (
            len(value) < 16
            or value in SECRET_PLACEHOLDERS
            or any(character in value for character in "<>{}$")
            or value.startswith(("os.environ", "os.getenv", "env(", "getenv("))
        ):
            continue
        return True
    return False


def _path_rule(path: str) -> str | None:
    pure = PurePosixPath(path)
    normalized_parts = tuple(part.casefold() for part in pure.parts)
    name = normalized_parts[-1]
    normalized_path = "/".join(normalized_parts)
    suffix = pure.suffix.casefold()
    stem = pure.stem.casefold()

    if name == ".env" or (name.startswith(".env.") and normalized_path != ".env.example"):
        return "environment_file"
    if normalized_parts[0] == "data" and normalized_path not in ALLOWED_DATA_FILES:
        return "private_data"
    if suffix in RASTER_IMAGE_SUFFIXES and path not in ALLOWED_RASTER_FILES:
        return "raster_image"
    if any(part in PRIVATE_DIRECTORY_COMPONENTS for part in normalized_parts[:-1]):
        return "private_artifact_directory"
    if name.startswith("events.out.tfevents"):
        return "tensorboard_event"
    if "manifest" in stem and suffix in TABULAR_DATA_SUFFIXES | {".json"}:
        return "image_level_manifest"
    if any(
        fragment in stem for fragment in IMAGE_LEVEL_NAME_FRAGMENTS
    ) and suffix in TABULAR_DATA_SUFFIXES | {".json"}:
        return "image_level_artifact"
    if suffix in TABULAR_DATA_SUFFIXES:
        return "tabular_data_artifact"
    if suffix in MODEL_ARTIFACT_SUFFIXES:
        return "model_artifact"
    return None


def audit_repository_privacy(repository: str | Path) -> dict[str, Any]:
    """Return a deterministic report without echoing private file contents."""

    repository = Path(repository).resolve()
    tracked_entries = _tracked_entries(repository)
    violations: list[dict[str, Any]] = []
    for path, mode, object_id, stage in tracked_entries:
        if stage != "0":
            violations.append({"path": path, "rule": "unmerged_index_entry"})
            continue
        if mode not in REGULAR_FILE_MODES:
            violations.append({"path": path, "rule": "non_regular_file"})
            continue
        rule = _path_rule(path)
        if rule is not None:
            violations.append({"path": path, "rule": rule})
            continue
        if path in ALLOWED_RASTER_FILES:
            continue

        content = _read_index_blob(repository, object_id)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            violations.append({"path": path, "rule": "unreviewed_binary_file"})
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if LOCAL_HOME_PATTERN.search(line):
                violations.append({"line": line_number, "path": path, "rule": "local_home_path"})
            if _contains_high_confidence_secret(line):
                violations.append({"line": line_number, "path": path, "rule": "secret_content"})

    violations.sort(key=lambda item: (item["path"], item["rule"], item.get("line", 0)))
    return {
        "status": "failed" if violations else "ok",
        "tracked_files": len(tracked_entries),
        "violations": violations,
    }
