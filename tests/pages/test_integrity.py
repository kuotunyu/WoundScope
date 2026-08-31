from __future__ import annotations

import importlib
import json
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
    return (
        module.BuildResult,
        module.PagesAuditError,
        module.build_site,
        module.compare_publish_trees,
        module.record_central_seal,
        module.seal_review,
        module.verify_publish_tree,
    )


def _git_stdout(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _site_source_sha() -> str:
    return _git_stdout("rev-parse", "HEAD")


def _source_date_epoch(site_source_sha: str) -> int:
    return int(_git_stdout("show", "-s", "--format=%ct", site_source_sha))


def build_for_test(output: Path):
    _build_result, _pages_audit_error, build_site, *_rest = _integrity_exports()
    site_source_sha = _site_source_sha()
    return build_site(REPOSITORY, output, site_source_sha, _source_date_epoch(site_source_sha))


def _manifest_payload(build_result) -> dict[str, object]:
    return json.loads((build_result.publish / "pages-manifest.json").read_text("utf-8"))


def _sbom_payload(build_result) -> dict[str, object]:
    return json.loads((build_result.publish / "sbom.spdx.json").read_text("utf-8"))


def _write_review_reports(reports: Path) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    for filename in (
        "toolchain.json",
        "network.json",
        "axe.json",
        "keyboard.json",
        "contrast.json",
        "browser-summary.json",
    ):
        (reports / filename).write_text("{}\n", encoding="utf-8", newline="\n")
    (reports / "zoom.json").write_text(
        json.dumps(
            {
                "content_reflow_emulation": [],
                "manual_browser_zoom_200_percent": [
                    {
                        "browser": "chromium",
                        "revision": "1234",
                        "reviewer": "kuotunyu",
                        "status": "PASS",
                    },
                    {
                        "browser": "firefox",
                        "revision": "1538",
                        "reviewer": "kuotunyu",
                        "status": "PASS",
                    },
                    {
                        "browser": "webkit",
                        "revision": "2336",
                        "reviewer": "kuotunyu",
                        "status": "PASS",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    screenshot = reports / "screenshots" / "overview.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\n")


def _init_temp_git_repository(repository: Path) -> str:
    subprocess.run(["git", "init"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "kuotunyu"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "61350295+kuotunyu@users.noreply.github.com"],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8", newline="\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repository, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def test_integrity_graph_is_acyclic_and_exact(tmp_path: Path) -> None:
    build_result = build_for_test(tmp_path / "one")
    manifest = _manifest_payload(build_result)
    sbom = _sbom_payload(build_result)
    manifest_paths = {item["path"] for item in manifest["files"]}
    sbom_paths = {item["fileName"].removeprefix("./") for item in sbom["files"]}

    assert "pages-manifest.json" not in manifest_paths
    assert "sbom.spdx.json" in manifest_paths
    assert "pages-manifest.json" not in sbom_paths
    assert "sbom.spdx.json" not in sbom_paths
    assert len(manifest_paths) == 8
    assert len(sbom_paths) == 7
    assert build_result.site_source_sha == _site_source_sha()
    assert build_result.publish_tree_sha256 == manifest["publish_tree_sha256"]
    assert "manifest_sha256" not in manifest
    assert "manifest_bytes" not in manifest


def test_manifest_records_sbom_hash_and_tree_digest_for_the_same_eight_files(
    tmp_path: Path,
) -> None:
    (
        _build_result,
        _pages_audit_error,
        _build_site,
        _compare_publish_trees,
        _record_central_seal,
        _seal_review,
        verify_publish_tree,
    ) = _integrity_exports()
    build_result = build_for_test(tmp_path / "manifest")
    manifest = _manifest_payload(build_result)
    verified = verify_publish_tree(build_result.publish)
    sbom_entry = next(item for item in manifest["files"] if item["path"] == "sbom.spdx.json")

    assert sbom_entry["sha256"] == verified.sbom_sha256
    assert sbom_entry["bytes"] == (build_result.publish / "sbom.spdx.json").stat().st_size
    assert manifest["publish_tree_sha256"] == verified.publish_tree_sha256
    assert manifest["site_source_sha"] == verified.site_source_sha
    assert "pages-manifest.json" not in {item["path"] for item in manifest["files"]}


def test_two_clean_builds_are_byte_identical(tmp_path: Path) -> None:
    _build_result, _pages_audit_error, _build_site, compare_publish_trees, *_rest = (
        _integrity_exports()
    )
    left = build_for_test(tmp_path / "left")
    right = build_for_test(tmp_path / "right")

    compare_publish_trees(left.publish, right.publish)

    assert left.publish_tree_sha256 == right.publish_tree_sha256
    assert left.manifest_sha256 == right.manifest_sha256
    assert left.sbom_sha256 == right.sbom_sha256


def test_seal_review_writes_receipt_outside_publish_and_copies_only_allowed_reports(
    tmp_path: Path,
) -> None:
    (
        _build_result,
        _pages_audit_error,
        _build_site,
        _compare_publish_trees,
        _record_central_seal,
        seal_review,
        verify_publish_tree,
    ) = _integrity_exports()
    build_result = build_for_test(tmp_path / "publish")
    reports = tmp_path / "reports"
    export_root = tmp_path / "export"
    _write_review_reports(reports)

    receipt = seal_review(build_result.publish, reports, export_root)
    verified = verify_publish_tree(export_root / "publish")
    receipt_payload = json.loads(receipt.read_text("utf-8"))

    assert receipt == export_root / "review-receipt.json"
    assert receipt_payload["site_source_sha"] == verified.site_source_sha
    assert receipt_payload["manifest_sha256"] == verified.manifest_sha256
    assert receipt_payload["sbom_sha256"] == verified.sbom_sha256
    assert receipt_payload["publish_tree_sha256"] == verified.publish_tree_sha256
    assert not (export_root / "publish" / "review-receipt.json").exists()
    assert sorted(
        path.relative_to(export_root / "reports").as_posix()
        for path in (export_root / "reports").rglob("*")
        if path.is_file()
    ) == sorted(
        [
            "axe.json",
            "browser-summary.json",
            "contrast.json",
            "keyboard.json",
            "network.json",
            "screenshots/overview.png",
            "toolchain.json",
            "zoom.json",
        ]
    )


def test_record_central_seal_requires_explicit_approval_id_and_matching_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        _build_result,
        pages_audit_error,
        _build_site,
        _compare_publish_trees,
        record_central_seal,
        _seal_review,
        _verify_publish_tree,
    ) = _integrity_exports()
    repository = tmp_path / "repo"
    repository.mkdir()
    head_sha = _init_temp_git_repository(repository)
    export_root = tmp_path / "review-export"
    export_root.mkdir()
    (export_root / "publish").mkdir()
    (export_root / "reports").mkdir()
    receipt = export_root / "review-receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "evidence_peeled_commit": "1b3df3b516cc4d366dc9da3cb01e8d0a319be613",
                "evidence_tag_object": "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4",
                "manifest_sha256": "a" * 64,
                "publish_tree_sha256": "c" * 64,
                "sbom_sha256": "b" * 64,
                "site_source_sha": head_sha,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(repository)

    with pytest.raises(pages_audit_error, match="CENTRAL_APPROVAL_ID_INVALID"):
        record_central_seal(
            repository=repository,
            receipt=receipt,
            output=tmp_path / "CENTRAL_SEAL.json",
            approved_site_source=head_sha,
            reviewer="kuotunyu",
            approval_id="",
        )

    output = tmp_path / "CENTRAL_SEAL.json"
    written = record_central_seal(
        repository=repository,
        receipt=receipt,
        output=output,
        approved_site_source=head_sha,
        reviewer="kuotunyu",
        approval_id="central-20260831",
    )
    payload = json.loads(written.read_text("utf-8"))

    assert written == output
    assert payload["approval_id"] == "central-20260831"
    assert payload["reviewer"] == "kuotunyu"
    assert payload["site_source_sha"] == head_sha
    assert payload["decision"] == "approved"


def test_record_central_seal_refuses_dirty_tracked_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        _build_result,
        pages_audit_error,
        _build_site,
        _compare_publish_trees,
        record_central_seal,
        _seal_review,
        _verify_publish_tree,
    ) = _integrity_exports()
    repository = tmp_path / "repo"
    repository.mkdir()
    head_sha = _init_temp_git_repository(repository)
    export_root = tmp_path / "review-export"
    export_root.mkdir()
    (export_root / "publish").mkdir()
    (export_root / "reports").mkdir()
    receipt = export_root / "review-receipt.json"
    receipt.write_text(
        json.dumps({"site_source_sha": head_sha}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (repository / "tracked.txt").write_text("dirty\n", encoding="utf-8", newline="\n")
    monkeypatch.chdir(repository)

    with pytest.raises(pages_audit_error, match="GIT_DIRTY"):
        record_central_seal(
            repository=repository,
            receipt=receipt,
            output=tmp_path / "CENTRAL_SEAL.json",
            approved_site_source=head_sha,
            reviewer="kuotunyu",
            approval_id="central-20260831",
        )


def test_seal_review_rejects_report_symlink_like_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _import_module("scripts.pages_site.integrity")
    build_result = build_for_test(tmp_path / "publish")
    reports = tmp_path / "reports"
    _write_review_reports(reports)
    target = reports / "toolchain.json"
    original_lstat = module.Path.lstat

    class _FakeStat:
        st_mode = stat.S_IFLNK
        st_size = target.stat().st_size

    def fake_lstat(path: Path):
        if path == target:
            return _FakeStat()
        return original_lstat(path)

    monkeypatch.setattr(module.Path, "lstat", fake_lstat)

    with pytest.raises(module.PagesAuditError, match=r"REPORT_SYMLINK:toolchain\.json"):
        module.seal_review(build_result.publish, reports, tmp_path / "export")


def test_record_central_seal_requires_explicit_repository_and_exact_output_placement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _import_module("scripts.pages_site.integrity")
    repository = tmp_path / "repo"
    repository.mkdir()
    head_sha = _init_temp_git_repository(repository)
    export_root = tmp_path / "review-export"
    export_root.mkdir()
    (export_root / "publish").mkdir()
    (export_root / "reports").mkdir()
    receipt = export_root / "review-receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "evidence_peeled_commit": "1b3df3b516cc4d366dc9da3cb01e8d0a319be613",
                "evidence_tag_object": "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4",
                "manifest_sha256": "a" * 64,
                "publish_tree_sha256": "c" * 64,
                "sbom_sha256": "b" * 64,
                "site_source_sha": head_sha,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(module.PagesAuditError, match="CENTRAL_SEAL_PATH_INVALID"):
        module.record_central_seal(
            repository=repository,
            receipt=receipt,
            output=export_root / "CENTRAL_SEAL.json",
            approved_site_source=head_sha,
            reviewer="kuotunyu",
            approval_id="central-20260831",
        )

    written = module.record_central_seal(
        repository=repository,
        receipt=receipt,
        output=tmp_path / "CENTRAL_SEAL.json",
        approved_site_source=head_sha,
        reviewer="kuotunyu",
        approval_id="central-20260831",
    )

    assert written == tmp_path / "CENTRAL_SEAL.json"


def test_record_central_seal_rejects_non_owner_reviewer(tmp_path: Path) -> None:
    module = _import_module("scripts.pages_site.integrity")
    repository = tmp_path / "repo"
    repository.mkdir()
    head_sha = _init_temp_git_repository(repository)
    export_root = tmp_path / "review-export"
    export_root.mkdir()
    receipt = export_root / "review-receipt.json"
    receipt.write_text(
        json.dumps({"site_source_sha": head_sha}, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(module.PagesAuditError, match="CENTRAL_REVIEWER_INVALID"):
        module.record_central_seal(
            repository=repository,
            receipt=receipt,
            output=tmp_path / "CENTRAL_SEAL.json",
            approved_site_source=head_sha,
            reviewer="someone-else",
            approval_id="central-20260831",
        )
