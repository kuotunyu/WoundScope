"""Pinned sparse Git checkout for the official FUSeg source."""

from __future__ import annotations

import subprocess
from pathlib import Path

from woundscope.data_integrity import DataIntegrityError


def _run_git(arguments: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise DataIntegrityError(f"Git command failed: git {' '.join(arguments)}\n{detail}")
    return completed.stdout.strip()


def ensure_sparse_checkout(
    repository: str,
    revision: str,
    subdirectory: str,
    destination: str | Path,
) -> Path:
    """Create or verify a detached sparse checkout at an exact revision."""

    destination = Path(destination).resolve()
    if destination.exists() and not (destination / ".git").is_dir() and any(destination.iterdir()):
        raise DataIntegrityError(f"Refusing to overwrite non-Git data destination: {destination}")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        _run_git(["clone", "--filter=blob:none", "--no-checkout", repository, str(destination)])

    _run_git(["sparse-checkout", "init", "--cone"], cwd=destination)
    _run_git(["sparse-checkout", "set", subdirectory], cwd=destination)
    try:
        _run_git(["checkout", "--detach", revision], cwd=destination)
    except DataIntegrityError:
        _run_git(["fetch", "origin", revision, "--depth", "1"], cwd=destination)
        _run_git(["checkout", "--detach", revision], cwd=destination)
    actual = _run_git(["rev-parse", "HEAD"], cwd=destination)
    if actual != revision:
        raise DataIntegrityError(f"Pinned revision mismatch: expected {revision}, found {actual}")
    return destination / Path(subdirectory)
