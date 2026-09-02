from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPOSITORY / "site-review" / "package.json"
LOCKFILE_PATH = REPOSITORY / "site-review" / "pnpm-lock.yaml"


def _import_module(name: str):
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(REPOSITORY))
        return importlib.import_module(name)
    finally:
        sys.path[:] = original_path


def _exports():
    module = _import_module("scripts.verify_pages_review_package")
    return module.ReviewerPackagePolicyError, module.audit_review_package


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy_package_pair(tmp_path: Path) -> tuple[Path, Path]:
    package_path = tmp_path / "package.json"
    lockfile_path = tmp_path / "pnpm-lock.yaml"
    package_path.write_text(PACKAGE_PATH.read_text("utf-8"), encoding="utf-8", newline="\n")
    lockfile_path.write_text(LOCKFILE_PATH.read_text("utf-8"), encoding="utf-8", newline="\n")
    return package_path, lockfile_path


def test_audit_review_package_accepts_the_approved_pair() -> None:
    _error_type, audit_review_package = _exports()

    summary = audit_review_package(PACKAGE_PATH, LOCKFILE_PATH)

    assert summary["lifecycle_scripts"] == []
    assert summary["packages"] == {
        "@playwright/test": {
            "integrity": "sha512-DTcUc8qii+cpHvtOwggMtBRMjKZHXYWdw8syRYu2vtzuq4Wxphqq4NfCs5Zt44L6mA8rfDfj+PHnxFc/FeK6mQ==",
            "version": "1.62.1",
        },
        "axe-core": {
            "integrity": "sha512-UzGt8zg7Ny8djbYMhxl2zuEevVa7r2gJjYY5Lwr1xM7+XU2nd6CkIWFTVcCIbAP63vSz71NaVyyuSk9lHKcy0A==",
            "version": "4.13.0",
        },
        "fsevents": {
            "integrity": "sha512-xiqMQR4xAeHTuB9uWm+fFRcIOgKBMiOBP+eXiyT7jsgVCq1bkVygt00oASowB7EdtpOHaaPgKt812P9ab+DDKA==",
            "version": "2.3.2",
        },
        "playwright": {
            "integrity": "sha512-0M+L3LAD8/nm554LOla9Ayx0j0tmFZ0FBcoQ7F1VuVHpM/XpiC8RcDzBQB8W5+hA8L22THxELzeF+2WcUzvcLg==",
            "version": "1.62.1",
        },
        "playwright-core": {
            "integrity": "sha512-wPYSwEBJY9GHraISXqyqtx0na0LpO3XEX7jNDhntbex7tzUS7kLnZsOlFruFJB4Hi/rhDMjXGqHewDZ68nYZVw==",
            "version": "1.62.1",
        },
    }


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda payload: payload["scripts"].__setitem__("preinstall", "node preinstall.js"),
            "LIFECYCLE_SCRIPT",
        ),
        (
            lambda payload: payload["scripts"].__setitem__("Prepare", "node prepare.js"),
            "LIFECYCLE_SCRIPT",
        ),
        (
            lambda payload: payload["scripts"].__setitem__("lint", "ruff check"),
            "SCRIPT_MAP",
        ),
        (
            lambda payload: payload.__setitem__("dependencies", {"left-pad": "1.3.0"}),
            "DEPENDENCY_FIELD",
        ),
        (
            lambda payload: payload["devDependencies"].__setitem__("axe-core", "^4.13.0"),
            "DEV_DEPENDENCY_VERSION",
        ),
        (
            lambda payload: payload["devDependencies"].__setitem__("left-pad", "1.3.0"),
            "DEV_DEPENDENCY_MAP",
        ),
        (
            lambda payload: payload.__setitem__("description", "unexpected"),
            "MANIFEST_KEYS",
        ),
    ],
)
def test_audit_review_package_rejects_hostile_manifest_mutations(
    tmp_path: Path, mutate, code: str
) -> None:
    error_type, audit_review_package = _exports()
    package_path, lockfile_path = _copy_package_pair(tmp_path)
    payload = json.loads(package_path.read_text("utf-8"))
    mutate(payload)
    _write_json(package_path, payload)

    with pytest.raises(error_type) as excinfo:
        audit_review_package(package_path, lockfile_path)

    assert str(excinfo.value) == code


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        ("lockfileVersion: '9.0'", "lockfileVersion: '8.0'", "LOCKFILE_VERSION"),
        (
            "specifier: 1.62.1",
            "specifier: ^1.62.1",
            "LOCKFILE_SPECIFIER",
        ),
        (
            "sha512-UzGt8zg7Ny8djbYMhxl2zuEevVa7r2gJjYY5Lwr1xM7+XU2nd6CkIWFTVcCIbAP63vSz71NaVyyuSk9lHKcy0A==",
            "sha512-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==",
            "LOCKFILE_INTEGRITY",
        ),
        (
            "playwright-core@1.62.1:",
            "left-pad@1.3.0:",
            "LOCKFILE_PACKAGE",
        ),
        (
            "packages:\n",
            "patchedDependencies:\n  axe-core@4.13.0: patches/axe.patch\n\npackages:\n",
            "LOCKFILE_FORBIDDEN_SECTION",
        ),
    ],
)
def test_audit_review_package_rejects_hostile_lockfile_mutations(
    tmp_path: Path, old: str, new: str, code: str
) -> None:
    error_type, audit_review_package = _exports()
    package_path, lockfile_path = _copy_package_pair(tmp_path)
    mutated = lockfile_path.read_text("utf-8").replace(old, new, 1)
    assert mutated != lockfile_path.read_text("utf-8")
    lockfile_path.write_text(mutated, encoding="utf-8", newline="\n")

    with pytest.raises(error_type) as excinfo:
        audit_review_package(package_path, lockfile_path)

    assert str(excinfo.value) == code


def test_cli_audits_the_pair_from_outside_repo_cwd(tmp_path: Path) -> None:
    package_path, lockfile_path = _copy_package_pair(tmp_path)
    environment = dict(os.environ)
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / "scripts" / "verify_pages_review_package.py"),
            "--package",
            str(package_path),
            "--lockfile",
            str(lockfile_path),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["lifecycle_scripts"] == []
