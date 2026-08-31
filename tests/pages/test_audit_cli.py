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
TABLE_REGION_OPEN = (
    '<div class="table-scroll" tabindex="0" role="region" '
    'aria-labelledby="evidence-table-caption">'
)
TABLE_OPEN = '<table aria-describedby="evidence-summary">'
TABLE_CAPTION = (
    '<caption id="evidence-table-caption">'
    "Locked Official Validation aggregate comparison</caption>"
)
EXPECTED_TITLES = {
    "index.html": "WoundScope | 靜態研究成果展示",
    "404.html": "WoundScope | 找不到此頁面",
}


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


def _rewrite_manifest_and_sbom_for_current_tree(publish: Path) -> None:
    module = _import_module("scripts.pages_site.integrity")
    manifest_payload = json.loads((publish / "pages-manifest.json").read_text("utf-8"))
    site_source_sha = manifest_payload["site_source_sha"]
    source_date_epoch = manifest_payload["source_date_epoch"]
    sbom_records = module._collect_records(publish, include_manifest=False, include_sbom=False)
    (publish / "sbom.spdx.json").write_text(
        json.dumps(
            module._expected_spdx_payload(site_source_sha, source_date_epoch, sbom_records),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_records = module._collect_records(publish, include_manifest=False, include_sbom=True)
    publish_tree_sha256 = module._tree_digest(manifest_records)
    (publish / "pages-manifest.json").write_text(
        json.dumps(
            module._expected_manifest_payload(
                site_source_sha,
                source_date_epoch,
                manifest_records,
                publish_tree_sha256,
                repository=None,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _rename_css_and_rewrite_publish(publish: Path, css_text: str) -> str:
    assets = publish / "assets"
    original_css = next(assets.glob("site-*.css"))
    new_bytes = css_text.encode("utf-8")
    new_name = f"site-{hashlib.sha256(new_bytes).hexdigest()[:16]}.css"
    (assets / new_name).write_bytes(new_bytes)
    for html_name in ("index.html", "404.html"):
        html_path = publish / html_name
        html_path.write_text(
            html_path.read_text("utf-8").replace(original_css.name, new_name),
            encoding="utf-8",
            newline="\n",
        )
    original_css.unlink()
    _rewrite_manifest_and_sbom_for_current_tree(publish)
    return new_name


def _publish_css_name(publish: Path) -> str:
    return next((publish / "assets").glob("site-*.css")).name


def _publish_svg_name(publish: Path) -> str:
    return next((publish / "assets").glob("model-comparison-*.svg")).name


def _expected_csp_meta_tag() -> str:
    module = _import_module("scripts.pages_site.integrity")
    return f'<meta http-equiv="Content-Security-Policy" content="{module.EXPECTED_CSP}">'


def _write_mutated_html_and_rewrite(
    publish: Path,
    *,
    old: str,
    new: str,
    count: int = 1,
    html_name: str = "index.html",
) -> None:
    html_path = publish / html_name
    html_path.write_text(
        html_path.read_text("utf-8").replace(old, new, count),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(publish)


def _inject_duplicate_attribute(
    html_text: str,
    *,
    original: str,
    duplicate: str,
) -> str:
    return html_text.replace(original, f"{original} {duplicate}", 1)


def _replace_focus_fragment(html_text: str, original: str, replacement: str) -> str:
    mutated = html_text.replace(original, replacement, 1)
    assert mutated != html_text
    return mutated


def _mutate_focus_region(html_text: str, mutation: str) -> str:
    replacements = {
        "missing_region_contract": (TABLE_REGION_OPEN, '<div class="table-scroll">'),
        "wrong_region_class": (
            TABLE_REGION_OPEN,
            '<div class="table-pane" tabindex="0" role="region" '
            'aria-labelledby="evidence-table-caption">',
        ),
        "duplicate_region": (
            TABLE_REGION_OPEN,
            f"{TABLE_REGION_OPEN}</div>{TABLE_REGION_OPEN}",
        ),
        "missing_tabindex": (TABLE_REGION_OPEN, TABLE_REGION_OPEN.replace(' tabindex="0"', "")),
        "wrong_tabindex": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace('tabindex="0"', 'tabindex="-1"'),
        ),
        "positive_tabindex": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace('tabindex="0"', 'tabindex="1"'),
        ),
        "missing_role": (TABLE_REGION_OPEN, TABLE_REGION_OPEN.replace(' role="region"', "")),
        "wrong_role": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace('role="region"', 'role="group"'),
        ),
        "missing_aria_labelledby": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace(' aria-labelledby="evidence-table-caption"', ""),
        ),
        "broken_aria_labelledby": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace(
                'aria-labelledby="evidence-table-caption"',
                'aria-labelledby="missing-caption"',
            ),
        ),
        "outside_heading_target": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace(
                'aria-labelledby="evidence-table-caption"',
                'aria-labelledby="evidence-title"',
            ),
        ),
        "missing_caption_id": (
            TABLE_CAPTION,
            TABLE_CAPTION.replace(' id="evidence-table-caption"', ""),
        ),
        "wrong_caption_id": (
            TABLE_CAPTION,
            TABLE_CAPTION.replace('id="evidence-table-caption"', 'id="wrong-caption"'),
        ),
        "duplicate_caption_target": (TABLE_CAPTION, f"{TABLE_CAPTION}{TABLE_CAPTION}"),
        "hidden_caption_target": (
            TABLE_CAPTION,
            TABLE_CAPTION.replace("<caption ", "<caption hidden "),
        ),
        "empty_caption_target": (
            TABLE_CAPTION,
            '<caption id="evidence-table-caption"></caption>',
        ),
        "other_div_zero_tabindex": (
            '<div class="page-shell">',
            '<div class="page-shell" tabindex="0">',
        ),
        "other_div_positive_tabindex": (
            '<div class="page-shell">',
            '<div class="page-shell" tabindex="2">',
        ),
        "extra_region_attribute": (
            TABLE_REGION_OPEN,
            TABLE_REGION_OPEN.replace(">", ' id="unexpected-region">'),
        ),
        "anchor_tabindex_exception": (
            '<a class="skip-link" href="#main-content">',
            '<a class="skip-link" href="#main-content" tabindex="0">',
        ),
    }
    if mutation in replacements:
        return _replace_focus_fragment(html_text, *replacements[mutation])
    if mutation == "non_caption_target":
        without_caption_id = _replace_focus_fragment(
            html_text,
            TABLE_CAPTION,
            TABLE_CAPTION.replace(' id="evidence-table-caption"', ""),
        )
        return _replace_focus_fragment(
            without_caption_id,
            '<p id="evidence-summary" class="figure-caption">',
            '<p id="evidence-table-caption" class="figure-caption">',
        )
    if mutation == "caption_outside_table":
        original = f"{TABLE_OPEN}\n            {TABLE_CAPTION}"
        replacement = f"{TABLE_CAPTION}\n          {TABLE_OPEN}"
        return _replace_focus_fragment(html_text, original, replacement)
    if mutation == "caption_outside_region":
        original = f"{TABLE_REGION_OPEN}\n          {TABLE_OPEN}\n            {TABLE_CAPTION}"
        replacement = f"{TABLE_CAPTION}\n        {TABLE_REGION_OPEN}\n          {TABLE_OPEN}"
        return _replace_focus_fragment(html_text, original, replacement)
    if mutation == "caption_in_wrong_table":
        without_caption = _replace_focus_fragment(html_text, TABLE_CAPTION, "")
        return _replace_focus_fragment(
            without_caption,
            "</table>\n        </div>",
            f"</table>\n          <table>{TABLE_CAPTION}</table>\n        </div>",
        )
    if mutation == "table_outside_region":
        empty_region = _replace_focus_fragment(
            html_text,
            TABLE_REGION_OPEN,
            f"{TABLE_REGION_OPEN}</div>",
        )
        return _replace_focus_fragment(
            empty_region,
            "</table>\n        </div>",
            "</table>",
        )
    raise AssertionError(f"unknown focus-region mutation: {mutation}")


def _mutate_html_structure(html_text: str, mutation: str) -> str:
    if mutation == "caption_closes_div":
        return _replace_focus_fragment(
            html_text,
            TABLE_CAPTION,
            TABLE_CAPTION.replace("</caption>", "</div></caption>"),
        )
    if mutation == "caption_closes_table":
        return _replace_focus_fragment(
            html_text,
            TABLE_CAPTION,
            TABLE_CAPTION.replace("</caption>", "</table></caption>"),
        )
    if mutation == "caption_closes_caption_then_div":
        return _replace_focus_fragment(
            html_text,
            TABLE_CAPTION,
            TABLE_CAPTION.replace("</caption>", "</caption></div></caption>"),
        )
    if mutation == "unmatched_close":
        return _replace_focus_fragment(html_text, "</body>", "</aside></body>")
    if mutation == "misnested_region_table":
        return _replace_focus_fragment(
            html_text,
            "</table>\n        </div>",
            "</div>\n        </table>",
        )
    if mutation == "extra_closing_div":
        return _replace_focus_fragment(html_text, "</body>", "</div></body>")
    if mutation == "unclosed_html_eof":
        return _replace_focus_fragment(html_text, "</html>\n", "")
    if mutation == "explicit_void_end":
        aggregate_image_end = 'height="520" loading="lazy">'
        return _replace_focus_fragment(
            html_text,
            aggregate_image_end,
            f"{aggregate_image_end}</img>",
        )
    if mutation == "nonvoid_startend":
        return _replace_focus_fragment(
            html_text,
            '<div class="page-shell">',
            '<div class="page-shell"/>',
        )
    raise AssertionError(f"unknown HTML-structure mutation: {mutation}")


def _move_head_line_after_head(html_text: str, line_prefix: str) -> str:
    lines = html_text.splitlines(keepends=True)
    line = next(line for line in lines if line.startswith(line_prefix))
    without_line = _replace_focus_fragment(html_text, line, "")
    return _replace_focus_fragment(without_line, "</head>\n", f"</head>\n{line}")


def _mutate_document_skeleton(html_text: str, mutation: str) -> str:
    html_open = '<html lang="zh-Hant-TW">'
    if mutation == "missing_doctype":
        return _replace_focus_fragment(html_text, "<!doctype html>\n", "")
    if mutation == "duplicate_doctype":
        return _replace_focus_fragment(
            html_text,
            "<!doctype html>\n",
            "<!doctype html>\n<!doctype html>\n",
        )
    if mutation == "wrong_doctype":
        return _replace_focus_fragment(html_text, "<!doctype html>", "<!doctype svg>")
    if mutation == "late_doctype":
        without_doctype = _replace_focus_fragment(html_text, "<!doctype html>\n", "")
        return _replace_focus_fragment(
            without_doctype,
            "</html>\n",
            "<!doctype html>\n</html>\n",
        )
    if mutation == "missing_html_root":
        without_open = _replace_focus_fragment(html_text, f"{html_open}\n", "")
        return _replace_focus_fragment(without_open, "</html>\n", "")
    if mutation == "duplicate_html_root":
        return _replace_focus_fragment(
            html_text,
            "</html>\n",
            f"</html>\n{html_open}</html>\n",
        )
    if mutation == "wrong_root_lang":
        return _replace_focus_fragment(
            html_text,
            html_open,
            '<html lang="en">',
        )
    if mutation == "missing_head":
        without_open = _replace_focus_fragment(html_text, "<head>\n", "")
        return _replace_focus_fragment(without_open, "</head>\n", "")
    if mutation == "missing_body":
        without_open = _replace_focus_fragment(html_text, "<body>\n", "")
        return _replace_focus_fragment(without_open, "</body>\n", "")
    if mutation == "swapped_head_body":
        return (
            html_text.replace("<head>", "<woundscope-head>", 1)
            .replace("</head>", "</woundscope-head>", 1)
            .replace("<body>", "<head>", 1)
            .replace("</body>", "</head>", 1)
            .replace("<woundscope-head>", "<body>", 1)
            .replace("</woundscope-head>", "</body>", 1)
        )
    if mutation == "nested_wrappers":
        return _replace_focus_fragment(
            html_text,
            "<body>\n",
            "<body>\n  <head></head><body></body>\n",
        )
    if mutation == "head_wrong_parent":
        wrapped = _replace_focus_fragment(
            html_text,
            "<head>",
            '<div class="page-shell"><head>',
        )
        return _replace_focus_fragment(wrapped, "</head>", "</head></div>")
    if mutation == "meta_outside_head":
        return _move_head_line_after_head(html_text, "  <meta charset=")
    if mutation == "title_outside_head":
        return _move_head_line_after_head(html_text, "  <title>")
    if mutation == "link_outside_head":
        return _move_head_line_after_head(html_text, "  <link rel=")
    if mutation == "body_semantic_outside_body":
        return _replace_focus_fragment(
            html_text,
            "<body>\n",
            "<p>outside body</p>\n<body>\n",
        )
    if mutation == "text_before_root":
        return f"outside root\n{html_text}"
    if mutation == "text_after_root":
        return _replace_focus_fragment(
            html_text,
            "</html>\n",
            "</html>\noutside root\n",
        )
    if mutation == "text_between_wrappers":
        return _replace_focus_fragment(
            html_text,
            "</head>\n<body>",
            "</head>\nroot text\n<body>",
        )
    raise AssertionError(f"unknown document-skeleton mutation: {mutation}")


def _make_windows_junction(link: Path, target: Path) -> bool:
    if os.name != "nt":
        return False
    target.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.returncode == 0


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

    expected_path = (
        "data" if relative_name == "data/rows.csv" else relative_name.replace(os.sep, "/")
    )
    assert _safe_error_text(excinfo.value) == f"{code}:{expected_path}"


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


def test_build_site_rejects_output_junction_without_touching_target(tmp_path: Path) -> None:
    pages_audit_error, build_site, _verify_publish_tree = _integrity_exports()
    site_source_sha = _git_stdout("rev-parse", "HEAD")
    source_date_epoch = int(_git_stdout("show", "-s", "--format=%ct", site_source_sha))
    target = tmp_path / "real-output"
    output = tmp_path / "publish"
    if not _make_windows_junction(output, target):
        pytest.skip("windows junction creation unavailable")

    with pytest.raises(pages_audit_error) as excinfo:
        build_site(REPOSITORY, output, site_source_sha, source_date_epoch)

    assert _safe_error_text(excinfo.value) == "OUTPUT_PATH_UNSAFE:publish"
    assert list(target.iterdir()) == []


def test_verify_publish_tree_rejects_root_reparse_point_from_lstat_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _import_module("scripts.pages_site.integrity")
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated")
    original_lstat = module.Path.lstat
    original_is_reparse_point = module._is_reparse_point

    class _FakeStat:
        st_mode = stat.S_IFDIR
        st_size = 0

    def fake_lstat(path: Path):
        if path == target_publish:
            return _FakeStat()
        return original_lstat(path)

    def fake_is_reparse_point(path_stat) -> bool:
        if path_stat.__class__ is _FakeStat:
            return True
        return original_is_reparse_point(path_stat)

    monkeypatch.setattr(module.Path, "lstat", fake_lstat)
    monkeypatch.setattr(module, "_is_reparse_point", fake_is_reparse_point)

    with pytest.raises(module.PagesAuditError) as excinfo:
        module.verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "TREE_SYMLINK:."


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (
            'href="https://github.com/kuotunyu/WoundScope"',
            'href="mailto:research@example.com"',
            "HTML_EXTERNAL_LINK:index.html",
        ),
        (
            'src="/WoundScope/assets/model-comparison-1eafa7c35b06928b.svg"',
            'src="https://example.com/remote.png"',
            "HTML_EXTERNAL_RESOURCE:index.html",
        ),
    ],
)
def test_publish_tree_rejects_denied_html_urls_even_when_dag_is_resynced(
    tmp_path: Path, old: str, new: str, code: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-html")
    _write_mutated_html_and_rewrite(target_publish, old=old, new=new)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == code


@pytest.mark.parametrize(
    ("html_name", "mutate"),
    [
        (
            "index.html",
            lambda text: text.replace(
                _expected_csp_meta_tag(),
                "",
                1,
            ),
        ),
        (
            "index.html",
            lambda text: text.replace(
                _expected_csp_meta_tag(),
                _expected_csp_meta_tag() + _expected_csp_meta_tag(),
                1,
            ),
        ),
        (
            "index.html",
            lambda text: text.replace(
                '<meta name="woundscope:candidate-canonical-url" '
                'content="https://kuotunyu.github.io/WoundScope/">',
                "",
                1,
            ),
        ),
        (
            "index.html",
            lambda text: text.replace(
                '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#151310">',
                '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#151310">\n'
                '  <meta name="robots" content="noindex">',
                1,
            ),
        ),
        (
            "index.html",
            lambda text: text.replace(
                "<title>WoundScope | 靜態研究成果展示</title>",
                '  <meta http-equiv="Refresh" content="0; url=https://example.com">\n'
                "  <title>WoundScope | 靜態研究成果展示</title>",
                1,
            ),
        ),
        (
            "404.html",
            lambda text: text.replace(
                '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#151310">',
                '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#151310">\n'
                '  <meta name="woundscope:candidate-canonical-url" '
                'content="https://kuotunyu.github.io/WoundScope/missing/">',
                1,
            ),
        ),
    ],
)
def test_publish_tree_rejects_meta_contract_drift_even_when_dag_is_resynced(
    tmp_path: Path, html_name: str, mutate
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-meta")
    html_path = target_publish / html_name
    html_path.write_text(
        mutate(html_path.read_text("utf-8")),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_META_MISMATCH:{html_name}"


@pytest.mark.parametrize(
    ("html_name", "original", "replacement"),
    [
        (
            "index.html",
            '<main id="main-content" tabindex="-1">',
            "",
        ),
        (
            "index.html",
            '<main id="main-content" tabindex="-1">',
            '<main id="wrong-main" tabindex="-1">',
        ),
        (
            "index.html",
            '<main id="main-content" tabindex="-1">',
            '<main id="main-content">',
        ),
        (
            "index.html",
            '<main id="main-content" tabindex="-1">',
            '<main id="main-content" tabindex="0">',
        ),
        (
            "index.html",
            '<main id="main-content" tabindex="-1">',
            '<main id="main-content" tabindex="-1" class="not-found">',
        ),
        (
            "index.html",
            '<main id="main-content" tabindex="-1">',
            '<main id="main-content" tabindex="-1"></main>'
            '<main id="main-content" tabindex="-1">',
        ),
        (
            "404.html",
            '<main id="main-content" class="not-found">',
            "",
        ),
        (
            "404.html",
            '<main id="main-content" class="not-found">',
            '<main id="wrong-main" class="not-found">',
        ),
        (
            "404.html",
            '<main id="main-content" class="not-found">',
            '<main id="main-content">',
        ),
        (
            "404.html",
            '<main id="main-content" class="not-found">',
            '<main id="main-content" class="not-found" tabindex="-1">',
        ),
        (
            "404.html",
            '<main id="main-content" class="not-found">',
            '<main id="main-content" class="not-found"></main>'
            '<main id="main-content" class="not-found">',
        ),
    ],
)
def test_publish_tree_rejects_main_contract_drift_even_when_dag_is_resynced(
    tmp_path: Path, html_name: str, original: str, replacement: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-main")
    html_path = target_publish / html_name
    original_text = html_path.read_text("utf-8")
    mutated_text = original_text.replace(original, replacement, 1)
    if not replacement:
        mutated_text = mutated_text.replace("</main>", "", 1)
    assert mutated_text != original_text
    html_path.write_text(mutated_text, encoding="utf-8", newline="\n")
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_MAIN_MISMATCH:{html_name}"


def test_publish_tree_accepts_exact_table_focus_region_contract(tmp_path: Path) -> None:
    _pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()

    verified = verify_publish_tree(audited_publish(tmp_path))

    assert verified.site_source_sha == _git_stdout("rev-parse", "HEAD")


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("missing_region_contract", "HTML_FOCUS_REGION_MISMATCH"),
        ("wrong_region_class", "HTML_FOCUS_REGION_MISMATCH"),
        ("duplicate_region", "HTML_FOCUS_REGION_MISMATCH"),
        ("missing_tabindex", "HTML_FOCUS_REGION_MISMATCH"),
        ("wrong_tabindex", "HTML_FOCUS_REGION_MISMATCH"),
        ("positive_tabindex", "HTML_FOCUS_REGION_MISMATCH"),
        ("missing_role", "HTML_FOCUS_REGION_MISMATCH"),
        ("wrong_role", "HTML_FOCUS_REGION_MISMATCH"),
        ("missing_aria_labelledby", "HTML_FOCUS_REGION_MISMATCH"),
        ("broken_aria_labelledby", "HTML_FOCUS_REGION_MISMATCH"),
        ("outside_heading_target", "HTML_FOCUS_REGION_MISMATCH"),
        ("missing_caption_id", "HTML_FOCUS_REGION_MISMATCH"),
        ("wrong_caption_id", "HTML_FOCUS_REGION_MISMATCH"),
        ("duplicate_caption_target", "HTML_FOCUS_REGION_MISMATCH"),
        ("hidden_caption_target", "HTML_ATTRIBUTE_INVALID"),
        ("empty_caption_target", "HTML_FOCUS_REGION_MISMATCH"),
        ("non_caption_target", "HTML_FOCUS_REGION_MISMATCH"),
        ("caption_outside_table", "HTML_FOCUS_REGION_MISMATCH"),
        ("caption_outside_region", "HTML_FOCUS_REGION_MISMATCH"),
        ("caption_in_wrong_table", "HTML_FOCUS_REGION_MISMATCH"),
        ("table_outside_region", "HTML_FOCUS_REGION_MISMATCH"),
        ("other_div_zero_tabindex", "HTML_FOCUS_REGION_MISMATCH"),
        ("other_div_positive_tabindex", "HTML_FOCUS_REGION_MISMATCH"),
        ("extra_region_attribute", "HTML_ATTRIBUTE_INVALID"),
        ("anchor_tabindex_exception", "HTML_ATTRIBUTE_INVALID"),
    ],
)
def test_publish_tree_rejects_focus_region_contract_drift_when_dag_is_resynced(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / f"mutated-focus-{mutation}"
    )
    html_path = target_publish / "index.html"
    html_path.write_text(
        _mutate_focus_region(html_path.read_text("utf-8"), mutation),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"{expected_code}:index.html"


@pytest.mark.parametrize(
    ("original", "duplicate"),
    [
        ('class="table-scroll"', 'CLASS="masked-region"'),
        ('tabindex="0"', 'TABINDEX="1"'),
        ('role="region"', 'ROLE="group"'),
        (
            'aria-labelledby="evidence-table-caption"',
            'ARIA-LABELLEDBY="evidence-title"',
        ),
        ('id="evidence-table-caption"', 'ID="masked-caption"'),
    ],
)
def test_publish_tree_rejects_focus_region_duplicate_attribute_masking(
    tmp_path: Path, original: str, duplicate: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-focus-duplicate"
    )
    html_path = target_publish / "index.html"
    html_path.write_text(
        _inject_duplicate_attribute(
            html_path.read_text("utf-8"),
            original=original,
            duplicate=duplicate,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_ATTRIBUTE_INVALID:index.html"


def test_not_found_rejects_any_table_focus_region_when_dag_is_resynced(
    tmp_path: Path,
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-404-focus-region"
    )
    html_path = target_publish / "404.html"
    injected = (
        f"{TABLE_REGION_OPEN}{TABLE_OPEN}{TABLE_CAPTION}</table></div>"
        '<main id="main-content" class="not-found">'
    )
    html_path.write_text(
        _replace_focus_fragment(
            html_path.read_text("utf-8"),
            '<main id="main-content" class="not-found">',
            injected,
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_FOCUS_REGION_MISMATCH:404.html"


@pytest.mark.parametrize(
    "mutation",
    [
        "caption_closes_div",
        "caption_closes_table",
        "caption_closes_caption_then_div",
        "unmatched_close",
        "misnested_region_table",
        "extra_closing_div",
        "unclosed_html_eof",
        "explicit_void_end",
        "nonvoid_startend",
    ],
)
def test_publish_tree_rejects_unbalanced_or_misnested_html_before_semantics(
    tmp_path: Path, mutation: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / f"mutated-structure-{mutation}"
    )
    html_path = target_publish / "index.html"
    html_path.write_text(
        _mutate_html_structure(html_path.read_text("utf-8"), mutation),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_STRUCTURE_INVALID:index.html"


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing_doctype",
        "duplicate_doctype",
        "wrong_doctype",
        "late_doctype",
        "missing_html_root",
        "duplicate_html_root",
        "wrong_root_lang",
        "missing_head",
        "missing_body",
        "swapped_head_body",
        "nested_wrappers",
        "head_wrong_parent",
        "meta_outside_head",
        "title_outside_head",
        "link_outside_head",
        "body_semantic_outside_body",
        "text_before_root",
        "text_after_root",
        "text_between_wrappers",
    ],
)
def test_publish_tree_rejects_document_skeleton_drift_before_semantics(
    tmp_path: Path, html_name: str, mutation: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"mutated-document-{html_name.removesuffix('.html')}-{mutation}",
    )
    html_path = target_publish / html_name
    html_path.write_text(
        _mutate_document_skeleton(html_path.read_text("utf-8"), mutation),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_STRUCTURE_INVALID:{html_name}"


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
@pytest.mark.parametrize("mutation", ["missing", "duplicate", "empty", "wrong"])
def test_publish_tree_rejects_exact_title_contract_drift(
    tmp_path: Path, html_name: str, mutation: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"mutated-title-{html_name.removesuffix('.html')}-{mutation}",
    )
    html_path = target_publish / html_name
    expected_title = EXPECTED_TITLES[html_name]
    title_tag = f"<title>{expected_title}</title>"
    replacements = {
        "missing": "",
        "duplicate": f"{title_tag}\n  {title_tag}",
        "empty": "<title></title>",
        "wrong": "<title>WoundScope | 錯誤頁面標題</title>",
    }
    html_path.write_text(
        _replace_focus_fragment(html_path.read_text("utf-8"), title_tag, replacements[mutation]),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_TITLE_MISMATCH:{html_name}"


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
def test_publish_tree_accepts_exact_decoded_title_text(tmp_path: Path, html_name: str) -> None:
    _pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"encoded-title-{html_name.removesuffix('.html')}",
    )
    html_path = target_publish / html_name
    expected_title = EXPECTED_TITLES[html_name]
    html_path.write_text(
        _replace_focus_fragment(
            html_path.read_text("utf-8"),
            f"<title>{expected_title}</title>",
            f"<title>{expected_title.replace('|', '&#124;')}</title>",
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    verify_publish_tree(target_publish)


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
@pytest.mark.parametrize("payload", ["<!--review-->", "<?review?>", "<![CDATA[review]]>"])
def test_publish_tree_rejects_non_data_syntax_in_title_rcdata(
    tmp_path: Path, html_name: str, payload: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"title-rcdata-{html_name.removesuffix('.html')}",
    )
    html_path = target_publish / html_name
    expected_title = EXPECTED_TITLES[html_name]
    html_path.write_text(
        _replace_focus_fragment(
            html_path.read_text("utf-8"),
            f"<title>{expected_title}</title>",
            f"<title>{expected_title}{payload}</title>",
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_TITLE_MISMATCH:{html_name}"


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
@pytest.mark.parametrize("payload", ["<!--review-->", "<?review?>", "<![CDATA[review]]>"])
def test_publish_tree_rejects_title_payload_when_parser_uses_non_data_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, html_name: str, payload: str
) -> None:
    integrity = _import_module("scripts.pages_site.integrity")
    rcdata_elements = tuple(
        tag for tag in integrity._HtmlAuditParser.RCDATA_CONTENT_ELEMENTS if tag != "title"
    )
    monkeypatch.setattr(integrity._HtmlAuditParser, "RCDATA_CONTENT_ELEMENTS", rcdata_elements)
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"title-callback-{html_name.removesuffix('.html')}",
    )
    html_path = target_publish / html_name
    expected_title = EXPECTED_TITLES[html_name]
    html_path.write_text(
        _replace_focus_fragment(
            html_path.read_text("utf-8"),
            f"<title>{expected_title}</title>",
            f"<title>{expected_title}{payload}</title>",
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(integrity.PagesAuditError) as excinfo:
        integrity.verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_TITLE_MISMATCH:{html_name}"


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
@pytest.mark.parametrize("payload", ["<!DOCTYPE html>", "<!DOCTYPE svg>"])
@pytest.mark.parametrize("fallback_dispatch", [False, True])
def test_publish_tree_keeps_title_declarations_out_of_document_doctype_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    html_name: str,
    payload: str,
    fallback_dispatch: bool,
) -> None:
    integrity = _import_module("scripts.pages_site.integrity")
    if fallback_dispatch:
        rcdata_elements = tuple(
            tag for tag in integrity._HtmlAuditParser.RCDATA_CONTENT_ELEMENTS if tag != "title"
        )
        monkeypatch.setattr(integrity._HtmlAuditParser, "RCDATA_CONTENT_ELEMENTS", rcdata_elements)
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"title-declaration-{html_name.removesuffix('.html')}",
    )
    html_path = target_publish / html_name
    expected_title = EXPECTED_TITLES[html_name]
    html_path.write_text(
        _replace_focus_fragment(
            html_path.read_text("utf-8"),
            f"<title>{expected_title}</title>",
            f"<title>{expected_title}{payload}</title>",
        ),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(integrity.PagesAuditError) as excinfo:
        integrity.verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_TITLE_MISMATCH:{html_name}"


@pytest.mark.parametrize("html_name", ["index.html", "404.html"])
@pytest.mark.parametrize("mutation", ["nested", "unclosed"])
def test_publish_tree_rejects_malformed_title_as_structure_error(
    tmp_path: Path, html_name: str, mutation: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path),
        tmp_path / f"malformed-title-{html_name.removesuffix('.html')}-{mutation}",
    )
    html_path = target_publish / html_name
    expected_title = EXPECTED_TITLES[html_name]
    title_tag = f"<title>{expected_title}</title>"
    replacements = {
        "nested": f"<title><title>{expected_title}</title></title>",
        "unclosed": f"<title>{expected_title}",
    }
    html_path.write_text(
        _replace_focus_fragment(html_path.read_text("utf-8"), title_tag, replacements[mutation]),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_STRUCTURE_INVALID:{html_name}"


@pytest.mark.parametrize(
    ("html_name", "mutate"),
    [
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original=f'href="/WoundScope/assets/{_publish_css_name(publish)}"',
                duplicate=f'href="/WoundScope/assets/{_publish_css_name(publish)}"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original=f'href="/WoundScope/assets/{_publish_css_name(publish)}"',
                duplicate=f'href="/WoundScope/assets/{_publish_svg_name(publish)}"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='href="#overview"',
                duplicate='href="#overview"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='href="https://github.com/kuotunyu/WoundScope"',
                duplicate='href="#overview"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original=f'src="/WoundScope/assets/{_publish_svg_name(publish)}"',
                duplicate='src="https://example.com/remote.png"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original=f'src="/WoundScope/assets/{_publish_svg_name(publish)}"',
                duplicate=f'src="/WoundScope/assets/{_publish_svg_name(publish)}"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='content="https://kuotunyu.github.io/WoundScope/"',
                duplicate='content="https://kuotunyu.github.io/WoundScope/"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='content="https://kuotunyu.github.io/WoundScope/"',
                duplicate='content="https://example.com/"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='http-equiv="Content-Security-Policy"',
                duplicate='http-equiv="Refresh"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='target="_blank"',
                duplicate='target="_self"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='rel="noopener noreferrer"',
                duplicate='rel="nofollow"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='rel="stylesheet"',
                duplicate='rel="preload"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='class="page-shell"',
                duplicate='class="mutated-shell"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='id="main-content"',
                duplicate='ID="masked-main"',
            ),
        ),
        (
            "index.html",
            lambda publish, text: _inject_duplicate_attribute(
                text,
                original='tabindex="-1"',
                duplicate='TABINDEX="0"',
            ),
        ),
    ],
)
def test_publish_tree_rejects_duplicate_html_attributes_before_meta_or_url_validation(
    tmp_path: Path, html_name: str, mutate
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-duplicate-attributes"
    )
    html_path = target_publish / html_name
    html_path.write_text(
        mutate(target_publish, html_path.read_text("utf-8")),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"HTML_ATTRIBUTE_INVALID:{html_name}"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda publish, text: text.replace(
            f'<link rel="stylesheet" href="/WoundScope/assets/{_publish_css_name(publish)}">',
            "",
            1,
        ),
        lambda publish, text: text.replace(
            f'<link rel="stylesheet" href="/WoundScope/assets/{_publish_css_name(publish)}">',
            f'<link rel="stylesheet" href="/WoundScope/assets/{_publish_css_name(publish)}">\n'
            f'  <link rel="stylesheet" href="/WoundScope/assets/{_publish_css_name(publish)}">',
            1,
        ),
        lambda publish, text: text.replace(
            f'<link rel="stylesheet" href="/WoundScope/assets/{_publish_css_name(publish)}">',
            f'<link rel="stylesheet" href="/WoundScope/assets/{_publish_svg_name(publish)}">',
            1,
        ).replace(
            f'src="/WoundScope/assets/{_publish_svg_name(publish)}"',
            f'src="/WoundScope/assets/{_publish_css_name(publish)}"',
            1,
        ),
        lambda publish, text: text.replace('href="#overview"', 'href="#evidence"', 1),
        lambda publish, text: text.replace(
            'href="https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.2"',
            'href="https://github.com/kuotunyu/WoundScope"',
            1,
        ),
        lambda publish, text: text.replace(
            '<li><span>Model card</span><a href="https://github.com/kuotunyu/WoundScope/blob/'
            '1b3df3b516cc4d366dc9da3cb01e8d0a319be613/MODEL_CARD.md" target="_blank" '
            'rel="noopener noreferrer">MODEL_CARD.md</a></li>',
            "",
            1,
        ),
    ],
)
def test_publish_tree_rejects_index_url_wiring_drift_even_when_dag_is_resynced(
    tmp_path: Path, mutate
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-index-wiring"
    )
    index_path = target_publish / "index.html"
    index_path.write_text(
        mutate(target_publish, index_path.read_text("utf-8")),
        encoding="utf-8",
        newline="\n",
    )
    _rewrite_manifest_and_sbom_for_current_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_WIRING_MISMATCH:index.html"


@pytest.mark.parametrize(
    "new_html",
    [
        '<img src="/WoundScope/assets/model-comparison-1eafa7c35b06928b.svg" alt="extra">'
        "</section>",
        '<a href="https://github.com/kuotunyu/WoundScope" target="_blank" '
        'rel="noopener noreferrer">Repository</a></section>',
    ],
)
def test_publish_tree_rejects_404_url_wiring_drift_even_when_dag_is_resynced(
    tmp_path: Path, new_html: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-404-wiring")
    _write_mutated_html_and_rewrite(
        target_publish,
        html_name="404.html",
        old="</section>",
        new=new_html,
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_WIRING_MISMATCH:404.html"


@pytest.mark.parametrize(
    "css_suffix",
    [
        '@import "https://example.com/theme.css";\n',
        '@im\\70 ort "https://example.com/theme.css";\n',
        ".hero{background:u\\72l (/WoundScope/x)}\n",
        ".hero{background:image-set(url(https://example.com/x.png) 1x)}\n",
    ],
)
def test_publish_tree_rejects_css_egress_variants_even_when_hash_and_dag_are_resynced(
    tmp_path: Path, css_suffix: str
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-css-egress")
    css_path = next((target_publish / "assets").glob("site-*.css"))
    new_name = _rename_css_and_rewrite_publish(
        target_publish,
        css_path.read_text("utf-8") + "\n" + css_suffix,
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == f"CSS_REMOTE_URL:assets/{new_name}"


def test_publish_tree_rejects_link_resource_hint_rel_even_when_dag_is_resynced(
    tmp_path: Path,
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-link-rel")
    _write_mutated_html_and_rewrite(
        target_publish,
        old='rel="stylesheet"',
        new='rel="preload"',
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "HTML_EXTERNAL_RESOURCE:index.html"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.setdefault("unexpected", "value"),
        lambda payload: payload["toolchain"].__setitem__("unexpected", "value"),
        lambda payload: payload["evidence"].pop("tag_object"),
    ],
)
def test_publish_tree_rejects_manifest_exact_structure_drift(tmp_path: Path, mutator) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-manifest-structure"
    )
    manifest_path = target_publish / "pages-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    mutator(manifest_payload)
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "MANIFEST_STRUCTURE:pages-manifest.json"


def test_publish_tree_rejects_source_date_epoch_cross_file_consistency_drift(
    tmp_path: Path,
) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(
        audited_publish(tmp_path), tmp_path / "mutated-manifest-epoch"
    )
    manifest_path = target_publish / "pages-manifest.json"
    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    manifest_payload["source_date_epoch"] = 0
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) == "SBOM_STRUCTURE:sbom.spdx.json"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.__setitem__("dataLicense", "MIT"),
        lambda payload: payload.__setitem__("name", "Wrong Name"),
        lambda payload: payload.__setitem__("SPDXID", "SPDXRef-WRONG"),
        lambda payload: payload["packages"][0].__setitem__(
            "downloadLocation", "https://example.com"
        ),
        lambda payload: payload["packages"][0].__setitem__("filesAnalyzed", False),
        lambda payload: payload["packages"][0].__setitem__("licenseDeclared", "MIT"),
        lambda payload: payload["packages"][0].__setitem__("copyrightText", "copyright"),
        lambda payload: payload["files"][0].__setitem__("SPDXID", "SPDXRef-File-Wrong"),
        lambda payload: payload["files"][0].__setitem__("copyrightText", "copyright"),
        lambda payload: payload["files"][0].__setitem__("licenseInfoInFiles", ["MIT"]),
        lambda payload: payload["relationships"][0].__setitem__(
            "spdxElementId", "SPDXRef-OtherPackage"
        ),
        lambda payload: payload["relationships"][0].__setitem__(
            "relatedSpdxElement", "SPDXRef-File-Wrong"
        ),
        lambda payload: payload["relationships"][0].__setitem__("relationshipType", "DEPENDS_ON"),
        lambda payload: payload["files"][0]["checksums"].append(
            {"algorithm": "SHA1", "checksumValue": "0" * 40}
        ),
        lambda payload: payload.setdefault("unexpected", "value"),
    ],
)
def test_publish_tree_rejects_spdx_exact_structure_drift(tmp_path: Path, mutator) -> None:
    pages_audit_error, _build_site, verify_publish_tree = _integrity_exports()
    target_publish = _clone_publish_tree(audited_publish(tmp_path), tmp_path / "mutated-sbom-exact")
    sbom_path = target_publish / "sbom.spdx.json"
    sbom_payload = json.loads(sbom_path.read_text("utf-8"))
    mutator(sbom_payload)
    sbom_path.write_text(
        json.dumps(sbom_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _sync_manifest_for_current_publish_tree(target_publish)

    with pytest.raises(pages_audit_error) as excinfo:
        verify_publish_tree(target_publish)

    assert _safe_error_text(excinfo.value) in {
        "SBOM_STRUCTURE:sbom.spdx.json",
        "SPDX_LICENSE_UNSAFE:sbom.spdx.json",
        "SBOM_CHECKSUM_MISMATCH:sbom.spdx.json",
    }
