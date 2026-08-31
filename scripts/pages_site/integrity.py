"""Build and audit the deterministic WoundScope Pages publish tree."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from .constants import (
    AUTHORED_SITE_FILES,
    BASE_PATH,
    CLAIM_BOUNDARY_VERSION,
    EXPECTED_BROWSER_REVISIONS,
    EXPECTED_CSP,
    EXPECTED_LICENSE_LENGTH,
    EXPECTED_LICENSE_SHA256,
    EXPECTED_PUBLIC_SVG_FILENAME,
    EXPECTED_PUBLIC_SVG_LENGTH,
    EXTERNAL_LINK_ALLOWLIST,
    FORBIDDEN_METRIC_LITERALS,
    LICENSE_BLOB,
    LICENSE_PATH,
    MANUAL_BROWSER_ZOOM_FIELD,
    MAX_CSS_BYTES,
    MAX_TOTAL_PUBLISH_BYTES,
    NETWORK_CONTRACT_VERSION,
    PUBLISH_FILE_BUDGETS,
    REVIEW_REPORT_FILES,
    REVIEW_SCREENSHOT_DIRECTORY,
    REVIEW_SCREENSHOT_SUFFIX,
    SITE_BUILD_MODE,
)
from .evidence import PEELED_COMMIT, PublicEvidence, load_public_evidence
from .render import render_site
from .svg_contract import load_verified_svg, verify_svg_bytes

_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_APPROVAL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_STYLE_HREF_RE = re.compile(r'href="/WoundScope/site\.css"')
_CSP_RE = re.compile(
    r'(<meta http-equiv="Content-Security-Policy" content=")([^"]+)(">)'
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?i)\b[A-Z]:[\\/][^\s<>'\"]+")
_UNIX_ABSOLUTE_PATH_RE = re.compile(r"/(?:Users|home|root)/[^\s<>'\"]+")
_SECRET_RE = re.compile(
    r"(?i)(?:\b(?:api[_-]?key|secret|token|password)\b\s*[:=]\s*\S+|\bsk-[A-Za-z0-9_-]{4,})"
)
_RUNTIME_JS_RE = re.compile(
    r"(?i)(?:fetch\(|xmlhttprequest|websocket|eventsource|sendbeacon|formdata|serviceworker)"
)
_CLIENT_DIGEST_RE = re.compile(
    r"(?i)(?:client-side cryptographic verification|runtime digest verification)"
)
_CSS_URL_RE = re.compile(r"url\s*\(", re.IGNORECASE)
_ALLOWED_ROOT_FILES = frozenset(
    {
        ".nojekyll",
        "index.html",
        "404.html",
        "LICENSE.txt",
        "THIRD_PARTY_NOTICES.txt",
        "sbom.spdx.json",
        "pages-manifest.json",
    }
)
_RASTER_SUFFIXES = frozenset(
    {".apng", ".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
)


class PagesAuditError(RuntimeError):
    """Stable, public-safe build and audit failure."""

    def __init__(self, code: str, public_path: str | None = None) -> None:
        self.code = code
        self.public_path = public_path
        message = code if public_path is None else f"{code}:{public_path}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class BuildResult:
    publish: Path
    site_source_sha: str
    manifest_sha256: str
    sbom_sha256: str
    publish_tree_sha256: str


@dataclass(frozen=True, slots=True)
class VerifiedPublish:
    publish: Path
    site_source_sha: str
    manifest_sha256: str
    sbom_sha256: str
    publish_tree_sha256: str


@dataclass(frozen=True, slots=True)
class _FileRecord:
    path: str
    bytes_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _Anchor:
    href: str
    rel: frozenset[str]
    target: str | None


class _HtmlAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.external_anchors: list[_Anchor] = []
        self.root_references: list[str] = []
        self.csp_values: list[str] = []
        self.forbidden_attributes = False
        self.forbidden_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag in {"script", "style", "form", "input", "iframe"}:
            self.forbidden_tags.append(tag)
        if any(name.startswith("on") for name, _value in attrs):
            self.forbidden_attributes = True
        for forbidden_attr in ("style", "contenteditable", "download"):
            if forbidden_attr in attr_map:
                self.forbidden_attributes = True
        if tag == "meta" and attr_map.get("http-equiv") == "Content-Security-Policy":
            content = attr_map.get("content")
            if content is not None:
                self.csp_values.append(content)
        for name in ("href", "src"):
            value = attr_map.get(name)
            if value is not None and value.startswith("/"):
                self.root_references.append(value)
        if tag == "a":
            href = attr_map.get("href")
            if href is not None and href.startswith("https://"):
                rel = frozenset(token for token in (attr_map.get("rel") or "").split() if token)
                self.external_anchors.append(
                    _Anchor(href=href, rel=rel, target=attr_map.get("target"))
                )


def _json_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _require_hex40(value: str, *, code: str) -> str:
    if _HEX40_RE.fullmatch(value) is None:
        raise PagesAuditError(code)
    return value


def _run_git_bytes(repository: Path, arguments: list[str], *, code: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise PagesAuditError(code) from error
    return completed.stdout


def _run_git_text(repository: Path, arguments: list[str], *, code: str) -> str:
    return _run_git_bytes(repository, arguments, code=code).decode("utf-8").strip()


def normalize_site_source_sha(repository: Path, site_source: str) -> str:
    resolved = _run_git_text(
        repository,
        ["rev-parse", f"{site_source}^{{commit}}"],
        code="SITE_SOURCE_SHA_INVALID",
    )
    return _require_hex40(resolved, code="SITE_SOURCE_SHA_INVALID")


def source_date_epoch_for_commit(repository: Path, site_source_sha: str) -> int:
    site_source_sha = _require_hex40(site_source_sha, code="SITE_SOURCE_SHA_INVALID")
    return int(
        _run_git_text(
            repository,
            ["show", "-s", "--format=%ct", site_source_sha],
            code="SITE_SOURCE_SHA_INVALID",
        )
    )


def _git_root_from_cwd() -> Path:
    root = _run_git_text(Path.cwd(), ["rev-parse", "--show-toplevel"], code="GIT_DIRTY")
    return Path(root)


def _git_tree_blob_id(repository: Path, commit_sha: str, public_path: str) -> str:
    entry = _run_git_text(repository, ["ls-tree", commit_sha, "--", public_path], code="SITE_SOURCE_READ")
    if not entry:
        raise PagesAuditError("SITE_SOURCE_READ", public_path=public_path)
    parts = entry.split(maxsplit=3)
    if len(parts) != 4 or parts[1] != "blob" or parts[3] != public_path:
        raise PagesAuditError("SITE_SOURCE_READ", public_path=public_path)
    return _require_hex40(parts[2], code="SITE_SOURCE_READ")


def _read_commit_blob(
    repository: Path,
    commit_sha: str,
    public_path: str,
    *,
    expected_blob: str | None = None,
) -> bytes:
    blob_id = _git_tree_blob_id(repository, commit_sha, public_path)
    if expected_blob is not None and blob_id != expected_blob:
        raise PagesAuditError("LICENSE_LOCK_MISMATCH", public_path="LICENSE.txt")
    return _run_git_bytes(repository, ["cat-file", "blob", blob_id], code="SITE_SOURCE_READ")


def _build_site_snapshot(
    repository: Path, site_source_sha: str, snapshot_root: Path
) -> tuple[Path, bytes]:
    site_root = snapshot_root / "site"
    site_root.mkdir(parents=True, exist_ok=True)
    for filename in AUTHORED_SITE_FILES:
        payload = _read_commit_blob(repository, site_source_sha, f"site/{filename}")
        (site_root / filename).write_bytes(payload)
    license_bytes = _read_commit_blob(
        repository,
        site_source_sha,
        LICENSE_PATH,
        expected_blob=LICENSE_BLOB,
    )
    if len(license_bytes) != EXPECTED_LICENSE_LENGTH:
        raise PagesAuditError("LICENSE_LOCK_MISMATCH", public_path="LICENSE.txt")
    if _sha256_bytes(license_bytes) != EXPECTED_LICENSE_SHA256:
        raise PagesAuditError("LICENSE_LOCK_MISMATCH", public_path="LICENSE.txt")
    return site_root, license_bytes


def _patch_html(document: bytes, css_filename: str) -> bytes:
    text = document.decode("utf-8")
    text, css_replacements = _STYLE_HREF_RE.subn(
        f'href="{BASE_PATH}assets/{css_filename}"',
        text,
        count=1,
    )
    if css_replacements != 1:
        raise PagesAuditError("HTML_SUBPATH", public_path="index.html")
    text, csp_replacements = _CSP_RE.subn(
        rf"\1{EXPECTED_CSP}\3",
        text,
        count=1,
    )
    if csp_replacements != 1:
        raise PagesAuditError("HTML_CSP_MISMATCH", public_path="index.html")
    return text.encode("utf-8")


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _file_record(path: Path, relative_path: str) -> _FileRecord:
    return _FileRecord(
        path=relative_path,
        bytes_size=path.stat().st_size,
        sha256=_sha256_path(path),
    )


def _css_relative_path(publish: Path) -> str:
    matches = sorted(path.name for path in (publish / "assets").glob("site-*.css"))
    if len(matches) != 1:
        raise PagesAuditError("TREE_MISSING_FILE", public_path="assets/site-[0-9a-f]{16}.css")
    return f"assets/{matches[0]}"


def _publish_paths(publish: Path) -> tuple[str, ...]:
    return (
        ".nojekyll",
        "index.html",
        "404.html",
        "LICENSE.txt",
        "THIRD_PARTY_NOTICES.txt",
        "sbom.spdx.json",
        "pages-manifest.json",
        _css_relative_path(publish),
        f"assets/{EXPECTED_PUBLIC_SVG_FILENAME}",
    )


def _collect_records(
    publish: Path, *, include_manifest: bool, include_sbom: bool
) -> tuple[_FileRecord, ...]:
    records: list[_FileRecord] = []
    for relative_path in _publish_paths(publish):
        if relative_path == "pages-manifest.json" and not include_manifest:
            continue
        if relative_path == "sbom.spdx.json" and not include_sbom:
            continue
        records.append(_file_record(publish / relative_path, relative_path))
    return tuple(records)


def _tree_digest(records: tuple[_FileRecord, ...]) -> str:
    payload_parts: list[bytes] = []
    for record in sorted(records, key=lambda item: item.path.encode("utf-8")):
        payload_parts.append(record.path.encode("utf-8"))
        payload_parts.append(b"\0")
        payload_parts.append(str(record.bytes_size).encode("ascii"))
        payload_parts.append(b"\0")
        payload_parts.append(record.sha256.encode("ascii"))
        payload_parts.append(b"\n")
    return _sha256_bytes(b"".join(payload_parts))


def _toolchain_payload() -> dict[str, str]:
    repository = _git_root_from_cwd()
    return {
        "git": _run_git_text(repository, ["--version"], code="GIT_COMMAND_FAILED"),
        "python": sys.version.split()[0],
    }


def _spdx_file_id(relative_path: str) -> str:
    return "SPDXRef-File-" + re.sub(r"[^A-Za-z0-9]+", "-", relative_path).strip("-")


def _spdx_payload(
    site_source_sha: str,
    source_date_epoch: int,
    file_records: tuple[_FileRecord, ...],
) -> bytes:
    created = datetime.fromtimestamp(source_date_epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    package_id = "SPDXRef-Package-WoundScopePages"
    files = []
    relationships = []
    for record in file_records:
        file_id = _spdx_file_id(record.path)
        files.append(
            {
                "SPDXID": file_id,
                "checksums": [{"algorithm": "SHA256", "checksumValue": record.sha256}],
                "fileName": f"./{record.path}",
                "licenseConcluded": "Apache-2.0",
                "licenseInfoInFiles": ["Apache-2.0"],
            }
        )
        relationships.append(
            {
                "relatedSpdxElement": file_id,
                "relationshipType": "CONTAINS",
                "spdxElementId": package_id,
            }
        )
    payload = {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": created,
            "creators": [f"Tool: woundscope-pages-builder/{sys.version.split()[0]}"],
        },
        "dataLicense": "CC0-1.0",
        "documentDescribes": [package_id],
        "documentNamespace": f"https://kuotunyu.github.io/WoundScope/spdx/{site_source_sha}",
        "files": files,
        "name": "WoundScope Static Pages Bundle",
        "packages": [
            {
                "SPDXID": package_id,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "Apache-2.0",
                "licenseDeclared": "Apache-2.0",
                "name": "woundscope-static-pages",
                "supplier": "Person: kuotunyu",
                "versionInfo": site_source_sha,
            }
        ],
        "relationships": relationships,
        "spdxVersion": "SPDX-2.3",
    }
    return _json_bytes(payload)


def _manifest_payload(
    site_source_sha: str,
    evidence: PublicEvidence,
    file_records: tuple[_FileRecord, ...],
    publish_tree_sha256: str,
) -> bytes:
    payload = {
        "base_path": BASE_PATH,
        "build_mode": SITE_BUILD_MODE,
        "claim_boundary_version": CLAIM_BOUNDARY_VERSION,
        "evidence": {
            "data_card_blob": evidence.provenance.data_card_blob,
            "model_card_blob": evidence.provenance.model_card_blob,
            "peeled_commit": evidence.provenance.peeled_commit,
            "readme_blob": evidence.provenance.readme_blob,
            "svg_blob": evidence.provenance.svg_blob,
            "tag_name": evidence.provenance.tag_name,
            "tag_object": evidence.provenance.tag_object,
        },
        "files": [
            {"bytes": record.bytes_size, "path": record.path, "sha256": record.sha256}
            for record in sorted(file_records, key=lambda item: item.path.encode("utf-8"))
        ],
        "network_contract_version": NETWORK_CONTRACT_VERSION,
        "publish_tree_sha256": publish_tree_sha256,
        "site_source_sha": site_source_sha,
        "toolchain": _toolchain_payload(),
    }
    return _json_bytes(payload)


def _classify_extra_path(relative_path: str) -> str:
    lower = relative_path.casefold()
    suffix = Path(relative_path).suffix.casefold()
    if lower.startswith(("data/", "artifacts/")):
        return "TREE_PRIVATE_DATA"
    if suffix in {".js", ".mjs"}:
        return "TREE_JAVASCRIPT"
    if suffix == ".wasm":
        return "TREE_WEBASSEMBLY"
    if suffix == ".map":
        return "TREE_SOURCE_MAP"
    if suffix in _RASTER_SUFFIXES:
        return "TREE_RASTER"
    return "TREE_EXTRA_FILE"


def _decode_utf8(path: Path, public_path: str) -> str:
    try:
        return path.read_text("utf-8")
    except UnicodeDecodeError as error:
        raise PagesAuditError("TREE_UTF8_INVALID", public_path=public_path) from error


def _assert_no_path_or_secret_leak(text: str, public_path: str) -> None:
    if _WINDOWS_ABSOLUTE_PATH_RE.search(text) or _UNIX_ABSOLUTE_PATH_RE.search(text):
        raise PagesAuditError("TREE_ABSOLUTE_PATH", public_path=public_path)
    if _SECRET_RE.search(text):
        raise PagesAuditError("TREE_SECRET", public_path=public_path)


def _assert_no_metric_drift(text: str, public_path: str) -> None:
    for token in FORBIDDEN_METRIC_LITERALS:
        if token in text:
            raise PagesAuditError("TREE_METRIC_DRIFT", public_path=public_path)


def _verify_inventory(publish: Path) -> tuple[str, str]:
    if not publish.is_dir():
        raise PagesAuditError("TREE_MISSING_FILE", public_path=".")
    css_relative: str | None = None
    svg_relative: str | None = None
    for path in publish.rglob("*"):
        relative_path = path.relative_to(publish).as_posix()
        stats = path.lstat()
        if stat.S_ISLNK(stats.st_mode):
            raise PagesAuditError("TREE_SYMLINK", public_path=relative_path)
        if stat.S_ISDIR(stats.st_mode):
            if relative_path == "assets":
                continue
            if relative_path == "data" or relative_path.startswith("data/"):
                continue
            if relative_path == "artifacts" or relative_path.startswith("artifacts/"):
                continue
            raise PagesAuditError("TREE_EXTRA_FILE", public_path=relative_path)
        if not stat.S_ISREG(stats.st_mode):
            raise PagesAuditError("TREE_SPECIAL_FILE", public_path=relative_path)
        if relative_path in _ALLOWED_ROOT_FILES:
            continue
        if relative_path.startswith("assets/"):
            if re.fullmatch(r"assets/site-[0-9a-f]{16}\.css", relative_path):
                if css_relative is not None:
                    raise PagesAuditError("TREE_EXTRA_FILE", public_path=relative_path)
                css_relative = relative_path
                continue
            if relative_path == f"assets/{EXPECTED_PUBLIC_SVG_FILENAME}":
                if svg_relative is not None:
                    raise PagesAuditError("TREE_EXTRA_FILE", public_path=relative_path)
                svg_relative = relative_path
                continue
        raise PagesAuditError(_classify_extra_path(relative_path), public_path=relative_path)
    for required in (
        ".nojekyll",
        "index.html",
        "404.html",
        "LICENSE.txt",
        "THIRD_PARTY_NOTICES.txt",
        "sbom.spdx.json",
        "pages-manifest.json",
    ):
        if not (publish / required).is_file():
            raise PagesAuditError("TREE_MISSING_FILE", public_path=required)
    if css_relative is None:
        raise PagesAuditError("TREE_MISSING_FILE", public_path="assets/site-[0-9a-f]{16}.css")
    if svg_relative is None:
        raise PagesAuditError(
            "TREE_MISSING_FILE",
            public_path=f"assets/{EXPECTED_PUBLIC_SVG_FILENAME}",
        )
    return css_relative, svg_relative


def _verify_html(path: Path, public_path: str) -> None:
    if path.stat().st_size > PUBLISH_FILE_BUDGETS[public_path]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path=public_path)
    text = _decode_utf8(path, public_path)
    _assert_no_path_or_secret_leak(text, public_path)
    parser = _HtmlAuditParser()
    parser.feed(text)
    parser.close()
    if parser.csp_values != [EXPECTED_CSP]:
        raise PagesAuditError("HTML_CSP_MISMATCH", public_path=public_path)
    if parser.forbidden_attributes or parser.forbidden_tags or _RUNTIME_JS_RE.search(text):
        raise PagesAuditError("TREE_JAVASCRIPT", public_path=public_path)
    if _CLIENT_DIGEST_RE.search(text):
        raise PagesAuditError("HTML_RUNTIME_VERIFICATION_CLAIM", public_path=public_path)
    for root_reference in parser.root_references:
        if not root_reference.startswith(BASE_PATH):
            raise PagesAuditError("HTML_SUBPATH", public_path=public_path)
    for anchor in parser.external_anchors:
        if (
            anchor.href not in EXTERNAL_LINK_ALLOWLIST
            or anchor.target != "_blank"
            or anchor.rel != {"noopener", "noreferrer"}
        ):
            raise PagesAuditError("HTML_EXTERNAL_LINK", public_path=public_path)


def _verify_css(path: Path, public_path: str) -> None:
    if path.stat().st_size > MAX_CSS_BYTES:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path=public_path)
    text = _decode_utf8(path, public_path)
    _assert_no_path_or_secret_leak(text, public_path)
    if _CSS_URL_RE.search(text):
        raise PagesAuditError("CSS_REMOTE_URL", public_path=public_path)
    expected_name = f"site-{_sha256_path(path)[:16]}.css"
    if path.name != expected_name:
        raise PagesAuditError("CSS_FILENAME_MISMATCH", public_path=public_path)


def _verify_license(path: Path) -> None:
    if path.stat().st_size != EXPECTED_LICENSE_LENGTH:
        raise PagesAuditError("LICENSE_LOCK_MISMATCH", public_path="LICENSE.txt")
    if _sha256_path(path) != EXPECTED_LICENSE_SHA256:
        raise PagesAuditError("LICENSE_LOCK_MISMATCH", public_path="LICENSE.txt")


def _verify_svg(path: Path) -> None:
    if path.stat().st_size != EXPECTED_PUBLIC_SVG_LENGTH:
        raise PagesAuditError("SVG_LENGTH", public_path=path.as_posix())
    evidence = load_public_evidence(_git_root_from_cwd())
    try:
        verified = verify_svg_bytes(path.read_bytes(), evidence, enforce_exact_bytes=True)
    except Exception as error:  # pragma: no cover
        raise PagesAuditError(str(error), public_path=path.as_posix()) from error
    if verified.public_filename != EXPECTED_PUBLIC_SVG_FILENAME:
        raise PagesAuditError("SVG_PUBLIC_FILENAME", public_path=path.as_posix())


def _verify_notices(path: Path) -> None:
    if path.stat().st_size > PUBLISH_FILE_BUDGETS["THIRD_PARTY_NOTICES.txt"]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path="THIRD_PARTY_NOTICES.txt")
    text = _decode_utf8(path, "THIRD_PARTY_NOTICES.txt")
    _assert_no_path_or_secret_leak(text, "THIRD_PARTY_NOTICES.txt")
    _assert_no_metric_drift(text, "THIRD_PARTY_NOTICES.txt")


def _verify_sbom(publish: Path, sbom_path: Path) -> str:
    if sbom_path.stat().st_size > PUBLISH_FILE_BUDGETS["sbom.spdx.json"]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path="sbom.spdx.json")
    payload = json.loads(_decode_utf8(sbom_path, "sbom.spdx.json"))
    files = payload.get("files")
    packages = payload.get("packages")
    if not isinstance(files, list) or not isinstance(packages, list) or len(packages) != 1:
        raise PagesAuditError("SBOM_STRUCTURE", public_path="sbom.spdx.json")
    package = packages[0]
    if package.get("licenseConcluded") != "Apache-2.0":
        raise PagesAuditError("SPDX_LICENSE_UNSAFE", public_path="sbom.spdx.json")
    if package.get("licenseDeclared") != "Apache-2.0":
        raise PagesAuditError("SPDX_LICENSE_UNSAFE", public_path="sbom.spdx.json")
    actual_records = {
        record.path: record
        for record in _collect_records(publish, include_manifest=False, include_sbom=False)
    }
    for item in files:
        file_name = item.get("fileName")
        if not isinstance(file_name, str) or not file_name.startswith("./"):
            raise PagesAuditError("SBOM_STRUCTURE", public_path="sbom.spdx.json")
        relative_path = file_name.removeprefix("./")
        if relative_path in {"sbom.spdx.json", "pages-manifest.json"}:
            raise PagesAuditError("SBOM_SELF_REFERENCE", public_path="sbom.spdx.json")
        record = actual_records.get(relative_path)
        if record is None:
            raise PagesAuditError("SBOM_FILE_SET_MISMATCH", public_path="sbom.spdx.json")
        checksums = item.get("checksums")
        if (
            not isinstance(checksums, list)
            or len(checksums) != 1
            or checksums[0].get("algorithm") != "SHA256"
            or checksums[0].get("checksumValue") != record.sha256
        ):
            raise PagesAuditError("SBOM_CHECKSUM_MISMATCH", public_path="sbom.spdx.json")
    if len(files) != len(actual_records):
        raise PagesAuditError("SBOM_FILE_SET_MISMATCH", public_path="sbom.spdx.json")
    return _sha256_path(sbom_path)


def _verify_manifest(publish: Path, manifest_path: Path) -> tuple[str, str]:
    if manifest_path.stat().st_size > PUBLISH_FILE_BUDGETS["pages-manifest.json"]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path="pages-manifest.json")
    payload = json.loads(_decode_utf8(manifest_path, "pages-manifest.json"))
    files = payload.get("files")
    if (
        payload.get("base_path") != BASE_PATH
        or payload.get("build_mode") != SITE_BUILD_MODE
        or payload.get("claim_boundary_version") != CLAIM_BOUNDARY_VERSION
        or payload.get("network_contract_version") != NETWORK_CONTRACT_VERSION
        or not isinstance(files, list)
    ):
        raise PagesAuditError("MANIFEST_STRUCTURE", public_path="pages-manifest.json")
    if "manifest_sha256" in payload or "manifest_bytes" in payload:
        raise PagesAuditError("MANIFEST_SELF_REFERENCE", public_path="pages-manifest.json")
    site_source_sha = payload.get("site_source_sha")
    if not isinstance(site_source_sha, str):
        raise PagesAuditError("MANIFEST_STRUCTURE", public_path="pages-manifest.json")
    _require_hex40(site_source_sha, code="MANIFEST_STRUCTURE")
    actual_records = {
        record.path: record
        for record in _collect_records(publish, include_manifest=False, include_sbom=True)
    }
    for item in files:
        relative_path = item.get("path")
        if relative_path == "pages-manifest.json":
            raise PagesAuditError("MANIFEST_SELF_REFERENCE", public_path="pages-manifest.json")
        if not isinstance(relative_path, str):
            raise PagesAuditError("MANIFEST_STRUCTURE", public_path="pages-manifest.json")
        record = actual_records.get(relative_path)
        if record is None:
            raise PagesAuditError("MANIFEST_FILE_SET_MISMATCH", public_path="pages-manifest.json")
        if item.get("bytes") != record.bytes_size or item.get("sha256") != record.sha256:
            raise PagesAuditError(
                "MANIFEST_FILE_RECORD_MISMATCH",
                public_path="pages-manifest.json",
            )
    if len(files) != len(actual_records):
        raise PagesAuditError("MANIFEST_FILE_SET_MISMATCH", public_path="pages-manifest.json")
    publish_tree_sha256 = _tree_digest(tuple(actual_records.values()))
    if payload.get("publish_tree_sha256") != publish_tree_sha256:
        raise PagesAuditError("TREE_DIGEST_MISMATCH", public_path="pages-manifest.json")
    return site_source_sha, _sha256_path(manifest_path)


def _report_records(reports: Path) -> tuple[_FileRecord, ...]:
    records: list[_FileRecord] = []
    for path in sorted(reports.rglob("*")):
        if path.is_file():
            records.append(_file_record(path, path.relative_to(reports).as_posix()))
    return tuple(records)


def _review_payload_sha256(
    publish_records: tuple[_FileRecord, ...], report_records: tuple[_FileRecord, ...]
) -> str:
    combined: list[_FileRecord] = []
    for record in publish_records:
        combined.append(
            _FileRecord(
                path=f"publish/{record.path}",
                bytes_size=record.bytes_size,
                sha256=record.sha256,
            )
        )
    for record in report_records:
        combined.append(
            _FileRecord(
                path=f"reports/{record.path}",
                bytes_size=record.bytes_size,
                sha256=record.sha256,
            )
        )
    return _tree_digest(tuple(combined))


def _verify_reports(reports: Path) -> tuple[_FileRecord, ...]:
    if not reports.is_dir():
        raise PagesAuditError("REPORT_MISSING", public_path="reports")
    for path in reports.rglob("*"):
        relative_path = path.relative_to(reports).as_posix()
        if path.is_dir():
            if relative_path == REVIEW_SCREENSHOT_DIRECTORY:
                continue
            if relative_path.startswith(f"{REVIEW_SCREENSHOT_DIRECTORY}/"):
                continue
            raise PagesAuditError("REPORT_EXTRA_FILE", public_path=relative_path)
        if relative_path in REVIEW_REPORT_FILES:
            continue
        if relative_path.startswith(f"{REVIEW_SCREENSHOT_DIRECTORY}/") and path.suffix == REVIEW_SCREENSHOT_SUFFIX:
            continue
        raise PagesAuditError("REPORT_EXTRA_FILE", public_path=relative_path)
    for filename in REVIEW_REPORT_FILES:
        if not (reports / filename).is_file():
            raise PagesAuditError("REPORT_MISSING", public_path=filename)
    zoom_payload = json.loads((reports / "zoom.json").read_text("utf-8"))
    manual_records = zoom_payload.get(MANUAL_BROWSER_ZOOM_FIELD)
    if not isinstance(manual_records, list):
        raise PagesAuditError("REPORT_MANUAL_ZOOM_REQUIRED", public_path="zoom.json")
    seen = {(item.get("browser"), str(item.get("revision")), item.get("status")) for item in manual_records}
    for browser, revision in EXPECTED_BROWSER_REVISIONS.items():
        if (browser, revision, "PASS") not in seen:
            raise PagesAuditError("REPORT_MANUAL_ZOOM_REQUIRED", public_path="zoom.json")
    return _report_records(reports)


def build_site(
    repository: Path,
    output: Path,
    site_source_sha: str,
    source_date_epoch: int,
) -> BuildResult:
    repository = repository.resolve()
    output = output.resolve()
    normalized_sha = normalize_site_source_sha(repository, site_source_sha)
    if output.exists():
        raise PagesAuditError("OUTPUT_EXISTS", public_path=output.name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="woundscope-pages-", dir=output.parent) as temp_dir:
        staging_root = Path(temp_dir)
        snapshot_root = staging_root / "snapshot"
        publish = staging_root / "publish"
        publish.mkdir()
        site_root, license_bytes = _build_site_snapshot(repository, normalized_sha, snapshot_root)
        evidence = load_public_evidence(repository)
        verified_svg = load_verified_svg(repository, evidence)
        rendered = render_site(evidence, verified_svg, normalized_sha, site_root)
        css_sha256 = _sha256_bytes(rendered.css)
        css_filename = f"site-{css_sha256[:16]}.css"
        _write_bytes(publish / ".nojekyll", b"")
        _write_bytes(publish / "index.html", _patch_html(rendered.index_html, css_filename))
        _write_bytes(publish / "404.html", _patch_html(rendered.not_found_html, css_filename))
        _write_bytes(publish / "LICENSE.txt", license_bytes)
        _write_bytes(publish / "THIRD_PARTY_NOTICES.txt", rendered.notices)
        _write_bytes(publish / "assets" / css_filename, rendered.css)
        _write_bytes(publish / "assets" / verified_svg.public_filename, verified_svg.bytes_value)
        sbom_records = _collect_records(publish, include_manifest=False, include_sbom=False)
        _write_bytes(
            publish / "sbom.spdx.json",
            _spdx_payload(normalized_sha, source_date_epoch, sbom_records),
        )
        manifest_records = _collect_records(publish, include_manifest=False, include_sbom=True)
        publish_tree_sha256 = _tree_digest(manifest_records)
        _write_bytes(
            publish / "pages-manifest.json",
            _manifest_payload(normalized_sha, evidence, manifest_records, publish_tree_sha256),
        )
        verified = verify_publish_tree(publish)
        publish.rename(output)
        return BuildResult(
            publish=output,
            site_source_sha=verified.site_source_sha,
            manifest_sha256=verified.manifest_sha256,
            sbom_sha256=verified.sbom_sha256,
            publish_tree_sha256=verified.publish_tree_sha256,
        )


def verify_publish_tree(publish: Path) -> VerifiedPublish:
    publish = publish.resolve()
    css_relative, svg_relative = _verify_inventory(publish)
    total_bytes = 0
    for relative_path in _publish_paths(publish):
        path = publish / relative_path
        if not path.is_file():
            raise PagesAuditError("TREE_MISSING_FILE", public_path=relative_path)
        total_bytes += path.stat().st_size
    if total_bytes > MAX_TOTAL_PUBLISH_BYTES:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path="publish")
    if (publish / ".nojekyll").stat().st_size != PUBLISH_FILE_BUDGETS[".nojekyll"]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path=".nojekyll")
    _verify_html(publish / "index.html", "index.html")
    _verify_html(publish / "404.html", "404.html")
    _verify_css(publish / css_relative, css_relative)
    _verify_license(publish / "LICENSE.txt")
    _verify_notices(publish / "THIRD_PARTY_NOTICES.txt")
    _verify_svg(publish / svg_relative)
    sbom_sha256 = _verify_sbom(publish, publish / "sbom.spdx.json")
    site_source_sha, manifest_sha256 = _verify_manifest(publish, publish / "pages-manifest.json")
    return VerifiedPublish(
        publish=publish,
        site_source_sha=site_source_sha,
        manifest_sha256=manifest_sha256,
        sbom_sha256=sbom_sha256,
        publish_tree_sha256=_tree_digest(
            _collect_records(publish, include_manifest=False, include_sbom=True)
        ),
    )


def compare_publish_trees(left: Path, right: Path) -> None:
    left_verified = verify_publish_tree(left)
    right_verified = verify_publish_tree(right)
    left_records = _collect_records(left_verified.publish, include_manifest=True, include_sbom=True)
    right_records = _collect_records(
        right_verified.publish,
        include_manifest=True,
        include_sbom=True,
    )
    if left_records != right_records:
        raise PagesAuditError("TREE_COMPARE_MISMATCH")


def seal_review(publish: Path, reports: Path, export_root: Path) -> Path:
    verified = verify_publish_tree(publish)
    report_records = _verify_reports(reports)
    export_root = export_root.resolve()
    if export_root.exists():
        raise PagesAuditError("OUTPUT_EXISTS", public_path=export_root.name)
    shutil.copytree(verified.publish, export_root / "publish")
    shutil.copytree(reports.resolve(), export_root / "reports")
    publish_records = _collect_records(
        export_root / "publish",
        include_manifest=True,
        include_sbom=True,
    )
    copied_report_records = _report_records(export_root / "reports")
    receipt = {
        "evidence_peeled_commit": PEELED_COMMIT,
        "evidence_tag_object": "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4",
        "manifest_sha256": verified.manifest_sha256,
        "publish_tree_sha256": verified.publish_tree_sha256,
        "report_hashes": [
            {"bytes": record.bytes_size, "path": record.path, "sha256": record.sha256}
            for record in sorted(copied_report_records, key=lambda item: item.path.encode("utf-8"))
        ],
        "review_payload_sha256": _review_payload_sha256(publish_records, copied_report_records),
        "sbom_sha256": verified.sbom_sha256,
        "site_source_sha": verified.site_source_sha,
    }
    receipt_path = export_root / "review-receipt.json"
    _write_bytes(receipt_path, _json_bytes(receipt))
    if report_records != copied_report_records:
        raise PagesAuditError("REPORT_COPY_MISMATCH", public_path="reports")
    return receipt_path


def _git_is_dirty(repository: Path) -> bool:
    return bool(_run_git_text(repository, ["status", "--porcelain=v1", "-uno"], code="GIT_DIRTY"))


def record_central_seal(
    receipt: Path,
    output: Path,
    approved_site_source: str,
    reviewer: str,
    approval_id: str,
) -> Path:
    approved_site_source = _require_hex40(approved_site_source, code="SITE_SOURCE_SHA_INVALID")
    if not _APPROVAL_ID_RE.fullmatch(approval_id):
        raise PagesAuditError("CENTRAL_APPROVAL_ID_INVALID")
    repository = _git_root_from_cwd()
    if _git_is_dirty(repository):
        raise PagesAuditError("GIT_DIRTY")
    if normalize_site_source_sha(repository, "HEAD") != approved_site_source:
        raise PagesAuditError("SITE_SOURCE_SHA_MISMATCH")
    receipt_payload = json.loads(receipt.read_text("utf-8"))
    if receipt_payload.get("site_source_sha") != approved_site_source:
        raise PagesAuditError("SITE_SOURCE_SHA_MISMATCH")
    output = output.resolve()
    if output.exists():
        raise PagesAuditError("OUTPUT_EXISTS", public_path=output.name)
    payload = {
        "approval_id": approval_id,
        "decision": "approved",
        "evidence_peeled_commit": receipt_payload.get("evidence_peeled_commit"),
        "evidence_tag_object": receipt_payload.get("evidence_tag_object"),
        "receipt_sha256": _sha256_bytes(receipt.read_bytes()),
        "reviewer": reviewer,
        "site_source_sha": approved_site_source,
    }
    _write_bytes(output, _json_bytes(payload))
    return output
