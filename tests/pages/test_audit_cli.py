from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


def _import_module(name: str):
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(REPOSITORY))
        return importlib.import_module(name)
    finally:
        sys.path[:] = original_path


def _integrity_exports():
    module = _import_module("scripts.pages_site.integrity")
    return module.PagesAuditError, module.build_site, module.verify_publish_tree


def _git_stdout(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def audited_publish(tmp_path: Path) -> Path:
    _pages_audit_error, build_site, _verify_publish_tree = _integrity_exports()
    site_source_sha = _git_stdout("rev-parse", "HEAD")
    source_date_epoch = int(_git_stdout("show", "-s", "--format=%ct", site_source_sha))
    output = tmp_path / f"publish-{len(list(tmp_path.iterdir()))}"
    build_result = build_site(REPOSITORY, output, site_source_sha, source_date_epoch)
    return build_result.publish


def _clone_publish_tree(source: Path, destination: Path) -> Path:
    copied = shutil.copytree(source, destination)
    return Path(copied)


def _safe_error_text(error: Exception) -> str:
    text = str(error)
    assert ("D" + ":\\") not in text
    assert str(REPOSITORY) not in text
    return text


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sync_manifest_for_current_publish_tree(publish: Path) -> None:
    manifest_path = publish / "pages-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    records: list[dict[str, object]] = []
    for item in manifest_payload["files"]:
        relative_path = item["path"]
        path = publish / relative_path
        records.append(
            {
                "bytes": path.stat().st_size,
                "path": relative_path,
                "sha256": _sha256_path(path),
            }
        )
    manifest_payload["files"] = sorted(records, key=lambda item: item["path"].encode("utf-8"))
    payload_parts: list[bytes] = []
    for item in manifest_payload["files"]:
        payload_parts.append(str(item["path"]).encode("utf-8"))
        payload_parts.append(b"\0")
        payload_parts.append(str(item["bytes"]).encode("ascii"))
        payload_parts.append(b"\0")
        payload_parts.append(str(item["sha256"]).encode("ascii"))
        payload_parts.append(b"\n")
    manifest_payload["publish_tree_sha256"] = hashlib.sha256(b"".join(payload_parts)).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sync_sbom_site_source(publish: Path, site_source_sha: str) -> None:
    sbom_path = publish / "sbom.spdx.json"
    sbom_payload = json.loads(sbom_path.read_text("utf-8"))
    sbom_payload["documentNamespace"] = (
        f"https://kuotunyu.github.io/WoundScope/spdx/{site_source_sha}"
    )
    sbom_payload["packages"][0]["versionInfo"] = site_source_sha
    sbom_path.write_text(
        json.dumps(sbom_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _sync_manifest_for_current_publish_tree(publish)


@pytest.mark.parametrize(
    ("relative_name", "code"),
    [
        ("extra.txt", "TREE_EXTRA_FILE"),
        ("assets/runtime.js", "TREE_JAVASCRIPT"),
        ("assets/runtime.wasm", "TREE_WEBASSEMBLY"),
        ("assets/example.webp", "TREE_RASTER"),
        ("assets/site.css.map", "TREE_SOURCE_MAP"),
        ("data/rows.csv", "TREE_PRIVATE_DATA"),
    ],
)
def test_publish_tree_fails_closed_on_extra_content(
    tmp_path: Path, relative_name: str, code: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    target = target_publish / relative_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"{code}:{relative_name.replace(os.sep, '/')}"


def test_publish_tree_rejects_missing_required_file(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    (target_publish / "index.html").unlink()

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_MISSING_FILE:index.html"


def test_publish_tree_rejects_symlink_mode_from_lstat_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _import_module("scripts.pages_site.integrity")
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    target = target_publish / "index.html"
    original_lstat = module.Path.lstat

    class _FakeStat:
        st_mode = stat.S_IFLNK
        st_size = target.stat().st_size

    def fake_lstat(path: Path):
        if path == target:
            return _FakeStat()
        return original_lstat(path)

    monkeypatch.setattr(module.Path, "lstat", fake_lstat)

    with pytest.raises(module.PagesAuditError) as excinfo:
        module.verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_SYMLINK:index.html"


def test_publish_tree_rejects_non_regular_mode_from_lstat_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _import_module("scripts.pages_site.integrity")
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    target = target_publish / "index.html"
    original_lstat = module.Path.lstat

    class _FakeStat:
        st_mode = stat.S_IFCHR
        st_size = target.stat().st_size

    def fake_lstat(path: Path):
        if path == target:
            return _FakeStat()
        return original_lstat(path)

    monkeypatch.setattr(module.Path, "lstat", fake_lstat)

    with pytest.raises(module.PagesAuditError) as excinfo:
        module.verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_SPECIAL_FILE:index.html"


def test_publish_tree_rejects_absolute_path_leak(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    index_path = target_publish / "index.html"
    index_path.write_text(
        index_path.read_text("utf-8").replace("Static research showcase", "C:/workspace/secret"),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_ABSOLUTE_PATH:index.html"


def test_publish_tree_rejects_secret_like_content(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    notices_path = target_publish / "THIRD_PARTY_NOTICES.txt"
    notices_path.write_text(
        notices_path.read_text("utf-8") + "\napi_key=sk-test-secret\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_SECRET:THIRD_PARTY_NOTICES.txt"


def test_publish_tree_rejects_metric_drift_outside_generated_evidence(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    (target_publish / "THIRD_PARTY_NOTICES.txt").write_text(
        "0.8508\n", encoding="utf-8", newline="\n"
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_METRIC_DRIFT:THIRD_PARTY_NOTICES.txt"


def test_publish_tree_rejects_external_link_drift_and_wrong_subpath(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    index_path = target_publish / "index.html"
    index_path.write_text(
        index_path.read_text("utf-8").replace(
            'href="https://github.com/kuotunyu/WoundScope"',
            'href="https://example.com/not-allowed"',
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(pages_audit_error, match="HTML_EXTERNAL_LINK"):
        verify_publish_tree(target_publish)

    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-subpath")
    index_path = target_publish / "index.html"
    index_path.write_text(
        index_path.read_text("utf-8").replace("/WoundScope/assets/", "/assets/", 1),
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(pages_audit_error, match="HTML_SUBPATH"):
        verify_publish_tree(target_publish)


def test_publish_tree_rejects_csp_and_css_remote_url_drift(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    index_path = target_publish / "index.html"
    index_path.write_text(
        index_path.read_text("utf-8").replace("script-src 'none'", "script-src 'self'"),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_CSP_MISMATCH:index.html"

    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-css")
    css_path = next((target_publish / "assets").glob("site-*.css"))
    css_path.write_text(
        css_path.read_text("utf-8") + "\n.hero{background:url(https://example.com/x.png)}\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(pages_audit_error, match="CSS_REMOTE_URL"):
        verify_publish_tree(target_publish)


def test_publish_tree_rejects_budget_overrun_and_license_tamper(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    (target_publish / "404.html").write_text("x" * 9000, encoding="utf-8", newline="\n")

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_BUDGET_EXCEEDED:404.html"

    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-license")
    (target_publish / "LICENSE.txt").write_text("tampered\n", encoding="utf-8", newline="\n")
    with pytest.raises(pages_audit_error, match="LICENSE_LOCK_MISMATCH"):
        verify_publish_tree(target_publish)


def test_publish_tree_rejects_sbom_manifest_and_tree_digest_tamper(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    sbom_path = target_publish / "sbom.spdx.json"
    sbom_payload = json.loads(sbom_path.read_text("utf-8"))
    sbom_payload["files"].append(
        {
            "checksums": [{"algorithm": "SHA256", "checksumValue": "a" * 64}],
            "fileName": "./sbom.spdx.json",
        }
    )
    sbom_path.write_text(
        json.dumps(sbom_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(pages_audit_error, match="SBOM_SELF_REFERENCE"):
        verify_publish_tree(target_publish)

    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-manifest")
    manifest_path = target_publish / "pages-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    manifest_payload["files"].append(
        {"bytes": 1, "path": "pages-manifest.json", "sha256": "b" * 64}
    )
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(pages_audit_error, match="MANIFEST_SELF_REFERENCE"):
        verify_publish_tree(target_publish)

    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-digest")
    manifest_path = target_publish / "pages-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    manifest_payload["publish_tree_sha256"] = "c" * 64
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(pages_audit_error, match="TREE_DIGEST_MISMATCH"):
        verify_publish_tree(target_publish)


def test_publish_tree_rejects_unsafe_spdx_license(tmp_path: Path) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    sbom_path = target_publish / "sbom.spdx.json"
    sbom_payload = json.loads(sbom_path.read_text("utf-8"))
    sbom_payload["packages"][0]["licenseConcluded"] = "LicenseRef-Proprietary"
    sbom_path.write_text(
        json.dumps(sbom_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(pages_audit_error, match="SPDX_LICENSE_UNSAFE"):
        verify_publish_tree(target_publish)


def test_build_cli_uses_safe_argv_and_leaves_no_output_on_failure(tmp_path: Path) -> None:
    output = tmp_path / "failed-build"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/build_pages_site.py",
            "--repository",
            ".",
            "--output",
            str(output),
            "--site-source",
            "not-a-sha",
        ],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "SITE_SOURCE_SHA_INVALID" in completed.stderr
    assert not output.exists()


def test_audit_cli_verify_round_trips_verified_tree(tmp_path: Path) -> None:
    publish = audited_publish(tmp_path)
    completed = subprocess.run(
        [sys.executable, "scripts/audit_pages_site.py", "verify", "--publish", str(publish)],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["site_source_sha"] == _git_stdout("rev-parse", "HEAD")
    assert payload["publish_tree_sha256"]
    assert completed.stderr == ""


def test_build_site_accepts_existing_empty_output_directory(tmp_path: Path) -> None:
    _pages_audit_error, build_site, verify_publish_tree = _integrity_exports()
    site_source_sha = _git_stdout("rev-parse", "HEAD")
    source_date_epoch = int(_git_stdout("show", "-s", "--format=%ct", site_source_sha))
    output = tmp_path / "publish"
    output.mkdir()

    build_result = build_site(REPOSITORY, output, site_source_sha, source_date_epoch)
    verified = verify_publish_tree(build_result.publish)

    assert build_result.publish == output
    assert verified.site_source_sha == site_source_sha


def test_build_site_uses_explicit_repository_outside_caller_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pages_audit_error, build_site, verify_publish_tree = _integrity_exports()
    site_source_sha = _git_stdout("rev-parse", "HEAD")
    source_date_epoch = int(_git_stdout("show", "-s", "--format=%ct", site_source_sha))
    monkeypatch.chdir(tmp_path)

    build_result = build_site(REPOSITORY, tmp_path / "publish", site_source_sha, source_date_epoch)
    verified = verify_publish_tree(build_result.publish)

    assert verified.site_source_sha == site_source_sha


def test_verify_publish_tree_succeeds_outside_repository_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    publish = audited_publish(tmp_path)
    monkeypatch.chdir(tmp_path)

    verified = verify_publish_tree(publish)

    assert verified.site_source_sha == _git_stdout("rev-parse", "HEAD")


@pytest.mark.parametrize(
    ("relative_name", "code"),
    [
        ("data", "TREE_PRIVATE_DATA"),
        ("artifacts", "TREE_PRIVATE_DATA"),
        ("tmp", "TREE_EXTRA_FILE"),
    ],
)
def test_publish_tree_rejects_extra_directories(
    tmp_path: Path, relative_name: str, code: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / f"dir-{relative_name}"
    )
    (target_publish / relative_name).mkdir(parents=True)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"{code}:{relative_name}"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.__setitem__("base_path", "/wrong/"),
        lambda payload: payload.__setitem__("build_mode", "dynamic"),
        lambda payload: payload.__setitem__("claim_boundary_version", "2026-09-01"),
        lambda payload: payload.__setitem__("network_contract_version", "2026-09-01"),
        lambda payload: payload.__setitem__("site_source_sha", "0" * 40),
        lambda payload: payload["toolchain"].__setitem__("git", "git version 0.0.0"),
        lambda payload: payload["toolchain"].__setitem__("python", "0.0.0"),
        lambda payload: payload["evidence"].__setitem__("tag_name", "v0.0.0"),
        lambda payload: payload["evidence"].__setitem__("tag_object", "0" * 40),
        lambda payload: payload["evidence"].__setitem__("peeled_commit", "0" * 40),
        lambda payload: payload["evidence"].__setitem__("readme_blob", "0" * 40),
        lambda payload: payload["evidence"].__setitem__("data_card_blob", "0" * 40),
        lambda payload: payload["evidence"].__setitem__("model_card_blob", "0" * 40),
        lambda payload: payload["evidence"].__setitem__("svg_blob", "0" * 40),
    ],
)
def test_publish_tree_rejects_manifest_locked_field_drift(tmp_path: Path, mutator) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-manifest-lock"
    )
    manifest_path = target_publish / "pages-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    original_site_source_sha = manifest_payload["site_source_sha"]
    mutator(manifest_payload)
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if manifest_payload["site_source_sha"] != original_site_source_sha:
        _sync_sbom_site_source(target_publish, manifest_payload["site_source_sha"])

    with pytest.raises(pages_audit_error, match="MANIFEST_STRUCTURE"):
        verify_publish_tree(target_publish)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.__setitem__("spdxVersion", "SPDX-2.2"),
        lambda payload: payload.__setitem__(
            "documentNamespace", "https://example.invalid/not-woundscope"
        ),
        lambda payload: payload.__setitem__("documentDescribes", ["SPDXRef-Other"]),
        lambda payload: payload["creationInfo"].__setitem__("created", "1970-01-01T00:00:00Z"),
        lambda payload: payload["creationInfo"].__setitem__("creators", ["Tool: wrong/0.0.0"]),
        lambda payload: payload["packages"][0].__setitem__("versionInfo", "0" * 40),
        lambda payload: payload["packages"][0].__setitem__("supplier", "Person: other"),
        lambda payload: payload["packages"][0].__setitem__("name", "wrong-pages"),
        lambda payload: payload["relationships"].__setitem__(
            0, payload["relationships"][0] | {"relationshipType": "DEPENDS_ON"}
        ),
        lambda payload: payload["files"][0].__setitem__("licenseConcluded", "NOASSERTION"),
    ],
)
def test_publish_tree_rejects_spdx_schema_drift(tmp_path: Path, mutator) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-sbom-lock")
    sbom_path = target_publish / "sbom.spdx.json"
    sbom_payload = json.loads(sbom_path.read_text("utf-8"))
    mutator(sbom_payload)
    sbom_path.write_text(
        json.dumps(sbom_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _sync_manifest_for_current_publish_tree(target_publish)

    with pytest.raises(pages_audit_error, match=r"SBOM_STRUCTURE|SPDX_LICENSE_UNSAFE"):
        verify_publish_tree(target_publish)
