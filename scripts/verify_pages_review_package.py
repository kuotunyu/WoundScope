from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

EXPECTED_MANIFEST = {
    "name": "woundscope-pages-review",
    "private": True,
    "version": "0.0.0",
    "type": "module",
    "packageManager": "pnpm@11.16.0",
    "engines": {
        "node": "24.16.0",
    },
    "scripts": {
        "check:toolchain": "node check-toolchain.mjs",
        "test": "playwright test",
    },
    "devDependencies": {
        "@playwright/test": "1.62.1",
        "axe-core": "4.13.0",
    },
}

EXPECTED_MANIFEST_KEYS = list(EXPECTED_MANIFEST)
LIFECYCLE_SCRIPT_NAMES = {
    "preinstall",
    "install",
    "postinstall",
    "prepublish",
    "preprepare",
    "prepare",
    "postprepare",
    "prepack",
    "postpack",
    "prepublishonly",
    "preversion",
    "version",
    "postversion",
}
FORBIDDEN_MANIFEST_FIELDS = {
    "dependencies": "DEPENDENCY_FIELD",
    "optionalDependencies": "DEPENDENCY_FIELD",
    "peerDependencies": "DEPENDENCY_FIELD",
    "bundledDependencies": "DEPENDENCY_FIELD",
    "bundleDependencies": "DEPENDENCY_FIELD",
    "pnpm": "DEPENDENCY_FIELD",
    "overrides": "DEPENDENCY_FIELD",
    "resolutions": "DEPENDENCY_FIELD",
}

EXPECTED_LOCKFILE_TEXT = "\n".join(
    [
        "lockfileVersion: '9.0'",
        "",
        "settings:",
        "  autoInstallPeers: true",
        "  excludeLinksFromLockfile: false",
        "",
        "importers:",
        "",
        "  .:",
        "    devDependencies:",
        "      '@playwright/test':",
        "        specifier: 1.62.1",
        "        version: 1.62.1",
        "      axe-core:",
        "        specifier: 4.13.0",
        "        version: 4.13.0",
        "",
        "packages:",
        "",
        "  '@playwright/test@1.62.1':",
        "    resolution: {integrity: sha512-DTcUc8qii+cpHvtOwggMtBRMjKZHXYWdw8syRYu2vtzuq4Wxphqq4NfCs5Zt44L6mA8rfDfj+PHnxFc/FeK6mQ==}",
        "    engines: {node: '>=18'}",
        "    dependencies:",
        "      playwright: 1.62.1",
        "",
        "  axe-core@4.13.0:",
        "    resolution: {integrity: sha512-UzGt8zg7Ny8djbYMhxl2zuEevVa7r2gJjYY5Lwr1xM7+XU2nd6CkIWFTVcCIbAP63vSz71NaVyyuSk9lHKcy0A==}",
        "",
        "  fsevents@2.3.2:",
        "    resolution: {integrity: sha512-xiqMQR4xAeHTuB9uWm+fFRcIOgKBMiOBP+eXiyT7jsgVCq1bkVygt00oASowB7EdtpOHaaPgKt812P9ab+DDKA==}",
        "    engines: {node: '^8.16.0 || ^10.6.0 || >=11.0.0'}",
        "    os: [darwin]",
        "",
        "  playwright@1.62.1:",
        "    resolution: {integrity: sha512-0M+L3LAD8/nm554LOla9Ayx0j0tmFZ0FBcoQ7F1VuVHpM/XpiC8RcDzBQB8W5+hA8L22THxELzeF+2WcUzvcLg==}",
        "    engines: {node: '>=18'}",
        "    dependencies:",
        "      playwright-core: 1.62.1",
        "    optionalDependencies:",
        "      fsevents: 2.3.2",
        "",
        "  playwright-core@1.62.1:",
        "    resolution: {integrity: sha512-wPYSwEBJY9GHraISXqyqtx0na0LpO3XEX7jNDhntbex7tzUS7kLnZsOlFruFJB4Hi/rhDMjXGqHewDZ68nYZVw==}",
        "    engines: {node: '>=18'}",
        "",
        "snapshots:",
        "",
        "  '@playwright/test@1.62.1':",
        "    dependencies:",
        "      playwright: 1.62.1",
        "",
        "  axe-core@4.13.0: {}",
        "",
        "  fsevents@2.3.2: {}",
        "",
        "  playwright@1.62.1:",
        "    dependencies:",
        "      playwright-core: 1.62.1",
        "    optionalDependencies:",
        "      fsevents: 2.3.2",
        "",
        "  playwright-core@1.62.1: {}",
        "",
    ]
)

EXPECTED_LOCKFILE_VERSION = "9.0"
EXPECTED_IMPORTER_SPECIFIERS = {
    "@playwright/test": "1.62.1",
    "axe-core": "4.13.0",
}
EXPECTED_PACKAGE_CLOSURE = {
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
EXPECTED_PACKAGE_KEYS = {
    "@playwright/test@1.62.1",
    "axe-core@4.13.0",
    "fsevents@2.3.2",
    "playwright@1.62.1",
    "playwright-core@1.62.1",
}
FORBIDDEN_LOCKFILE_SECTIONS = {
    "catalog",
    "catalogs",
    "overrides",
    "patchedDependencies",
    "packageExtensions",
    "onlyBuiltDependencies",
    "neverBuiltDependencies",
}
FORBIDDEN_LOCKFILE_SOURCE_PATTERN = re.compile(
    r"(?mi):\s*(workspace:|file:|link:|git\+|github:|https?:)"
)


class ReviewerPackagePolicyError(RuntimeError):
    pass


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_utf8(path: Path) -> tuple[bytes, str]:
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReviewerPackagePolicyError("UTF8") from exc
    return payload, text


def _raise(code: str) -> None:
    raise ReviewerPackagePolicyError(code)


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict):
        _raise("MANIFEST_KEYS")
    for field, code in FORBIDDEN_MANIFEST_FIELDS.items():
        if field in manifest:
            _raise(code)
    if list(manifest) != EXPECTED_MANIFEST_KEYS:
        _raise("MANIFEST_KEYS")
    scripts = manifest.get("scripts")
    if not isinstance(scripts, dict):
        _raise("SCRIPT_MAP")
    lifecycle = sorted(
        key for key in scripts if isinstance(key, str) and key.casefold() in LIFECYCLE_SCRIPT_NAMES
    )
    if lifecycle:
        _raise("LIFECYCLE_SCRIPT")
    if scripts != EXPECTED_MANIFEST["scripts"]:
        _raise("SCRIPT_MAP")
    if manifest.get("devDependencies") != EXPECTED_MANIFEST["devDependencies"]:
        dev_dependencies = manifest.get("devDependencies")
        if not isinstance(dev_dependencies, dict):
            _raise("DEV_DEPENDENCY_MAP")
        if set(dev_dependencies) != set(EXPECTED_MANIFEST["devDependencies"]):
            _raise("DEV_DEPENDENCY_MAP")
        _raise("DEV_DEPENDENCY_VERSION")
    comparison = dict(manifest)
    comparison.pop("scripts", None)
    comparison.pop("devDependencies", None)
    expected = dict(EXPECTED_MANIFEST)
    expected.pop("scripts", None)
    expected.pop("devDependencies", None)
    if comparison != expected:
        _raise("MANIFEST_KEYS")


def _extract_root_sections(lockfile_text: str) -> list[str]:
    return [
        match.group(1)
        for match in re.finditer(r"(?m)^(?!\s)([A-Za-z][A-Za-zA-Z0-9]*):", lockfile_text)
    ]


def _validate_lockfile_root(lockfile_text: str) -> None:
    sections = _extract_root_sections(lockfile_text)
    expected_sections = ["lockfileVersion", "settings", "importers", "packages", "snapshots"]
    if sections != expected_sections:
        if any(
            section in FORBIDDEN_LOCKFILE_SECTIONS
            for section in sections
            if section not in expected_sections
        ):
            _raise("LOCKFILE_FORBIDDEN_SECTION")
        _raise("LOCKFILE_FORBIDDEN_SECTION")
    if re.search(
        r"(?mi)^(catalog|catalogs|overrides|patchedDependencies|packageExtensions|onlyBuiltDependencies|neverBuiltDependencies):",
        lockfile_text,
    ):
        _raise("LOCKFILE_FORBIDDEN_SECTION")
    if FORBIDDEN_LOCKFILE_SOURCE_PATTERN.search(lockfile_text):
        _raise("LOCKFILE_FORBIDDEN_SECTION")


def _validate_lockfile_version(lockfile_text: str) -> None:
    match = re.search(r"(?m)^lockfileVersion:\s*'([^']+)'\s*$", lockfile_text)
    if match is None or match.group(1) != EXPECTED_LOCKFILE_VERSION:
        _raise("LOCKFILE_VERSION")


def _validate_importer_block(lockfile_text: str) -> None:
    importer_match = re.search(r"(?ms)^importers:\n\n(?P<body>.*?)^packages:\n", lockfile_text)
    if importer_match is None:
        _raise("LOCKFILE_SPECIFIER")
    body = importer_match.group("body")
    labels = re.findall(r"(?m)^ {6}(?:'([^']+)'|([^:\n]+)):\s*$", body)
    names = [(quoted or plain) for quoted, plain in labels]
    if names != list(EXPECTED_IMPORTER_SPECIFIERS):
        _raise("LOCKFILE_PACKAGE")
    for name, expected_version in EXPECTED_IMPORTER_SPECIFIERS.items():
        pattern = (
            rf"(?ms)^ {{6}}(?:'{re.escape(name)}'|{re.escape(name)}):\n"
            rf" {{8}}specifier: (?P<specifier>[^\n]+)\n"
            rf" {{8}}version: (?P<version>[^\n]+)\n"
        )
        match = re.search(pattern, body)
        if match is None:
            _raise("LOCKFILE_SPECIFIER")
        if match.group("specifier").strip() != expected_version:
            _raise("LOCKFILE_SPECIFIER")
        if match.group("version").strip() != expected_version:
            _raise("LOCKFILE_SPECIFIER")


def _extract_package_entries(lockfile_text: str) -> dict[str, str]:
    package_match = re.search(r"(?ms)^packages:\n\n(?P<body>.*?)^snapshots:\n", lockfile_text)
    if package_match is None:
        _raise("LOCKFILE_PACKAGE")
    body = package_match.group("body")
    entries: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    entry_pattern = re.compile(r"^  (?! )(?:'[^']+'|[^ '\n][^:\n]*):\n$")
    for line in body.splitlines(keepends=True):
        if entry_pattern.match(line):
            if current_name is not None:
                entries[current_name] = "".join(current_lines)
            current_name = line.strip().rstrip(":").strip("'")
            current_lines = []
            continue
        if current_name is None:
            if line.strip():
                _raise("LOCKFILE_PACKAGE")
            continue
        current_lines.append(line)
    if current_name is not None:
        entries[current_name] = "".join(current_lines)
    return entries


def _validate_package_entries(entries: dict[str, str]) -> None:
    if set(entries) != EXPECTED_PACKAGE_KEYS:
        _raise("LOCKFILE_PACKAGE")
    for key, body in entries.items():
        resolution = re.search(r"(?m)^    resolution: \{integrity: (?P<value>[^}]+)\}\s*$", body)
        if resolution is None:
            _raise("LOCKFILE_INTEGRITY")
        package_name, version = key.rsplit("@", 1)
        expected = EXPECTED_PACKAGE_CLOSURE[package_name]
        if resolution.group("value").strip() != expected["integrity"]:
            _raise("LOCKFILE_INTEGRITY")
        if version != expected["version"]:
            _raise("LOCKFILE_PACKAGE")


def audit_review_package(package_path: Path, lockfile_path: Path) -> dict[str, object]:
    manifest_bytes, manifest_text = _load_utf8(package_path)
    lockfile_bytes, lockfile_text = _load_utf8(lockfile_path)
    manifest = json.loads(manifest_text)
    _validate_manifest(manifest)
    _validate_lockfile_version(lockfile_text)
    _validate_lockfile_root(lockfile_text)
    _validate_importer_block(lockfile_text)
    _validate_package_entries(_extract_package_entries(lockfile_text))
    return {
        "lifecycle_scripts": [],
        "lockfile_sha256": _sha256_bytes(lockfile_bytes),
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "packages": EXPECTED_PACKAGE_CLOSURE,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--lockfile", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        result = audit_review_package(arguments.package, arguments.lockfile)
    except ReviewerPackagePolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
