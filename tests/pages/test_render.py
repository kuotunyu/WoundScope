from __future__ import annotations

import html
import importlib
import importlib.util
import json
import re
import sys
import traceback
from dataclasses import dataclass, replace
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
SITE_ROOT = REPOSITORY / "site"
AUTHORIZED_SITE_FILES = (
    "index.template.html",
    "404.template.html",
    "site.css",
    "links.allowlist.json",
    "THIRD_PARTY_NOTICES.txt",
)
EXPECTED_EXTERNAL_LINK_COUNT = 9
EXPECTED_CSP_FRAGMENT = "script-src 'none'"
EXPECTED_THEME_COLORS = (
    ("(prefers-color-scheme: light)", "#f4f0e8"),
    ("(prefers-color-scheme: dark)", "#151310"),
)
EXPECTED_NOTICES_TEXT = """WoundScope Static Research Showcase — Third-Party Notices

Bundled third-party runtime packages: none.
The production site contains authored HTML/CSS, WoundScope project material under Apache-2.0, and a WoundScope-authored aggregate SVG projected from the pinned v0.2.2 Git evidence object.

Aggregate research-fact attribution (not bundled software or redistributed data):
FUSeg / Foot Ulcer Segmentation Challenge, pinned public source revision 42a272dfe0679f20675e826385925cb7562934b6.
Publication: https://doi.org/10.1038/s41598-020-78799-w
Source: https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge

No FUSeg image, mask, patient/sample identifier, model weight, ONNX artifact, or image-level result is redistributed by this site. Apache-2.0 does not assert ownership of FUSeg or model artifacts.

Build/review-only tools are reported separately in the review artifact and are not production runtime components.
"""
FORBIDDEN_TAGS = frozenset({"audio", "button", "form", "iframe", "input", "source", "video"})
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"\bcolab\b", re.IGNORECASE),
    re.compile(r"\bhf\b", re.IGNORECASE),
    re.compile(r"hugging\s*face", re.IGNORECASE),
    re.compile(r"medical[- ]device", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class Anchor:
    href: str
    target: str | None
    rel: frozenset[str]


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[Anchor] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href is None:
            return
        rel = frozenset(token for token in (attr_map.get("rel") or "").split() if token)
        self.anchors.append(Anchor(href=href, target=attr_map.get("target"), rel=rel))


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.body_start_tags: list[str] = []
        self.headings: list[int] = []
        self.caption_count = 0
        self.table_th_scopes: list[str] = []
        self.forbidden_tags: list[str] = []
        self.has_inline_style_attr = False
        self.has_event_handler_attr = False
        self.has_contenteditable = False
        self.has_download_attr = False
        self.remote_canonical_hrefs: list[str] = []
        self.disallowed_link_rels: list[str] = []
        self.root_asset_refs: list[str] = []
        self.img_attrs: list[dict[str, str | None]] = []
        self.theme_colors: list[tuple[str | None, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "body":
            self.in_body = True
        elif self.in_body:
            self.body_start_tags.append(tag)
        if tag in FORBIDDEN_TAGS:
            self.forbidden_tags.append(tag)
        if tag == "caption":
            self.caption_count += 1
        if tag == "th":
            scope = attr_map.get("scope")
            if scope is not None:
                self.table_th_scopes.append(scope)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if tag == "img":
            self.img_attrs.append(attr_map)
        if "style" in attr_map:
            self.has_inline_style_attr = True
        if "contenteditable" in attr_map:
            self.has_contenteditable = True
        if "download" in attr_map:
            self.has_download_attr = True
        if any(name.startswith("on") for name in attr_map):
            self.has_event_handler_attr = True
        for value in attr_map.values():
            if value is not None and value.startswith("/assets/"):
                self.root_asset_refs.append(value)
        if tag == "link":
            rel_tokens = {
                token.casefold() for token in (attr_map.get("rel") or "").split() if token
            }
            href = attr_map.get("href")
            for token in ("preconnect", "prefetch", "preload"):
                if token in rel_tokens:
                    self.disallowed_link_rels.append(token)
            if (
                "canonical" in rel_tokens
                and href is not None
                and href.startswith(("http://", "https://"))
            ):
                self.remote_canonical_hrefs.append(href)
        if tag == "meta" and attr_map.get("name") == "theme-color":
            self.theme_colors.append((attr_map.get("media"), attr_map.get("content")))

    def handle_endtag(self, tag: str) -> None:
        if tag == "body":
            self.in_body = False


def _import_module(name: str):
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(REPOSITORY))
        spec = importlib.util.find_spec(name)
        assert spec is not None, f"{name} must exist"
        return importlib.import_module(name)
    finally:
        sys.path[:] = original_path


def _render_module():
    return _import_module("scripts.pages_site.render")


def _render_exports() -> tuple[type[Exception], object, object]:
    module = _render_module()
    return module.RenderContractError, module.escape_text, module.render_site


def _evidence_exports() -> tuple[object, object]:
    module = _import_module("scripts.pages_site")
    return module.load_public_evidence, _import_module(
        "scripts.pages_site.svg_contract"
    ).load_verified_svg


def collect_anchors(document: bytes) -> list[Anchor]:
    parser = _AnchorParser()
    parser.feed(document.decode("utf-8"))
    parser.close()
    return parser.anchors


def _parse_structure(document: bytes) -> _StructureParser:
    parser = _StructureParser()
    parser.feed(document.decode("utf-8"))
    parser.close()
    return parser


def _metric_tokens(evidence) -> set[str]:
    tokens: set[str] = set()
    metric_fields = (
        "dice_mean",
        "dice_sd",
        "dice_ci_low",
        "dice_ci_high",
        "iou_mean",
        "iou_sd",
        "precision_mean",
        "precision_sd",
        "recall_mean",
        "recall_sd",
        "specificity_mean",
        "specificity_sd",
    )
    for row in evidence.rows:
        for field_name in metric_fields:
            value = getattr(row, field_name)
            assert isinstance(value, Decimal)
            tokens.add(f"{value.quantize(Decimal('0.0001')):f}")
    return tokens


def _lf_bytes(text: str) -> bytes:
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _crlf_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")


def _make_site_copy(
    tmp_path: Path,
    *,
    crlf: bool = False,
    mutations: dict[str, str | bytes] | None = None,
    missing: set[str] | None = None,
) -> Path:
    mutations = mutations or {}
    missing = missing or set()
    copy_root = tmp_path / "site"
    copy_root.mkdir()
    for filename in AUTHORIZED_SITE_FILES:
        if filename in missing:
            continue
        original = mutations.get(filename, (SITE_ROOT / filename).read_bytes())
        if isinstance(original, bytes):
            payload = original
            if crlf:
                payload = _crlf_text(payload.decode("utf-8")).encode("utf-8")
        else:
            text = _crlf_text(original) if crlf else original
            payload = text.encode("utf-8")
        (copy_root / filename).write_bytes(payload)
    return copy_root


def _render(site_root: Path = SITE_ROOT, *, site_source_sha: str = "a" * 40):
    _error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    return render_site(
        evidence=evidence,
        verified_svg=verified_svg,
        site_source_sha=site_source_sha,
        site_root=site_root,
    )


def _assert_utf8_lf_only(payload: bytes) -> None:
    assert not payload.startswith(b"\xef\xbb\xbf")
    decoded = payload.decode("utf-8")
    assert "\ufeff" not in decoded
    assert b"\r" not in payload
    assert decoded.encode("utf-8") == payload


def _assert_public_error(excinfo: pytest.ExceptionInfo[Exception], expected_code: str) -> None:
    assert str(excinfo.value) == expected_code
    assert "D:\\" not in str(excinfo.value)
    assert str(SITE_ROOT) not in str(excinfo.value)


def _assert_sanitized_error(
    excinfo: pytest.ExceptionInfo[Exception],
    expected_code: str,
    *,
    expect_suppressed_context: bool,
) -> None:
    _assert_public_error(excinfo, expected_code)
    assert excinfo.value.__cause__ is None
    if expect_suppressed_context:
        assert excinfo.value.__suppress_context__ is True
    else:
        assert excinfo.value.__context__ is None
    chain_text = "".join(traceback.format_exception_only(type(excinfo.value), excinfo.value))
    assert "D:\\" not in chain_text
    assert str(SITE_ROOT) not in chain_text


def test_renderer_escapes_dynamic_values_and_separates_provenance() -> None:
    _error_type, escape_text, _render_site = _render_exports()
    rendered = _render()
    text = rendered.index_html.decode("utf-8")

    assert escape_text("<script>") == html.escape("<script>", quote=True) == "&lt;script&gt;"
    assert "Site source" in text and "Evidence source" in text
    assert text.index("<table") < text.index("model-comparison-")
    assert EXPECTED_CSP_FRAGMENT in text
    assert "<script" not in text.casefold()
    for expected_copy in (
        "WoundScope",
        "足部潰瘍二元語意分割的靜態研究成果展示",
        "研究用途 · 非 official-test · 非臨床效能",
        (
            "本頁只展示方法、可重現控制與鎖定 Official Validation 的彙總結果；"
            "不提供影像上傳、API、推論、模型或醫療建議。"
        ),
        "彙總證據",
        (
            "結果來自單一公開資料來源的 200 張 Official Validation；每個架構使用 "
            "seeds 42／43／44。Dice 95% CI 為 2,000 次 image-level percentile Bootstrap；"
            "因沒有 patient ID，無法校正同一病患多張影像的相關性。"
        ),
        (
            "這些是 observed research results，不是 official-test、外部、多中心或臨床表現，"
            "也不能推論診斷、治療、安全性或跨機構優勢。"
        ),
        (
            "公開邊界：code、methodology、aggregate evidence；不公開資料影像、weights、ONNX、"
            "image-level results 或 live model。"
        ),
    ):
        assert expected_copy in text


def test_only_exact_external_links_are_emitted() -> None:
    document = _render().index_html
    anchors = collect_anchors(document)
    allowlist_path = SITE_ROOT / "links.allowlist.json"

    assert allowlist_path.is_file()
    allowlist = json.loads(allowlist_path.read_text("utf-8"))
    external = [anchor for anchor in anchors if anchor.href.startswith("https://")]
    assert len(allowlist) == EXPECTED_EXTERNAL_LINK_COUNT
    assert {anchor.href for anchor in external} == set(allowlist)
    assert all(
        anchor.target == "_blank" and anchor.rel == {"noopener", "noreferrer"}
        for anchor in external
    )


def test_rendered_index_and_not_found_pages_remain_semantic_and_static() -> None:
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    rendered = _render()
    index_text = rendered.index_html.decode("utf-8")
    structure = _parse_structure(rendered.index_html)
    not_found_text = rendered.not_found_html.decode("utf-8")
    not_found_anchors = collect_anchors(rendered.not_found_html)

    assert structure.body_start_tags[0] == "a"
    assert structure.headings.count(1) == 1
    assert all(
        current <= previous + 1
        for previous, current in zip(structure.headings, structure.headings[1:], strict=False)
    )
    assert structure.caption_count >= 1
    assert structure.table_th_scopes
    assert all(scope in {"col", "row"} for scope in structure.table_th_scopes)
    assert not structure.forbidden_tags
    assert not structure.has_inline_style_attr
    assert not structure.has_event_handler_attr
    assert not structure.has_contenteditable
    assert not structure.has_download_attr
    assert not structure.disallowed_link_rels
    assert not structure.remote_canonical_hrefs
    assert not structure.root_asset_refs
    assert [img["src"] for img in structure.img_attrs] == [
        f"/WoundScope/assets/{verified_svg.public_filename}"
    ]
    assert "fetch(" not in index_text
    assert "javascript:" not in index_text.casefold()
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        assert pattern.search(index_text) is None

    assert "找不到此頁面" in not_found_text
    assert EXPECTED_CSP_FRAGMENT in not_found_text
    assert not_found_anchors == [Anchor(href="/WoundScope/", target=None, rel=frozenset())]
    assert "<script" not in not_found_text.casefold()


def test_site_source_contains_no_aggregate_metric_tokens() -> None:
    load_public_evidence, _load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)

    assert SITE_ROOT.is_dir()
    source_text = "\n".join(
        path.read_text("utf-8") for path in sorted(SITE_ROOT.rglob("*")) if path.is_file()
    )
    for token in _metric_tokens(evidence):
        assert token not in source_text


def test_renderer_normalizes_crlf_text_sources_to_utf8_lf_only(tmp_path: Path) -> None:
    site_root = _make_site_copy(tmp_path, crlf=True)
    rendered = _render(site_root)

    for payload in (
        rendered.index_html,
        rendered.not_found_html,
        rendered.css,
        rendered.notices,
    ):
        _assert_utf8_lf_only(payload)
    assert rendered.notices == _lf_bytes(EXPECTED_NOTICES_TEXT)


def test_renderer_wraps_missing_site_file_without_path_leak(tmp_path: Path) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    site_root = _make_site_copy(tmp_path, missing={"site.css"})

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_sanitized_error(excinfo, "SITE_FILE_READ", expect_suppressed_context=True)


def test_renderer_wraps_unreadable_site_file_without_path_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _render_module()
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    blocked = SITE_ROOT / "site.css"
    original_read_bytes = Path.read_bytes

    def fake_read_bytes(path: Path) -> bytes:
        if path == blocked:
            raise PermissionError(f"denied: {blocked}")
        return original_read_bytes(path)

    monkeypatch.setattr(module.Path, "read_bytes", fake_read_bytes)

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, SITE_ROOT)

    _assert_sanitized_error(excinfo, "SITE_FILE_READ", expect_suppressed_context=True)


def test_renderer_rejects_utf8_bom_without_path_or_cause_leak(tmp_path: Path) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    bom_payload = b"\xef\xbb\xbf" + (SITE_ROOT / "site.css").read_bytes()
    site_root = _make_site_copy(tmp_path, mutations={"site.css": bom_payload})

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_sanitized_error(excinfo, "SITE_FILE_BOM", expect_suppressed_context=False)


def test_renderer_rejects_invalid_utf8_without_path_or_cause_leak(tmp_path: Path) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    site_root = _make_site_copy(tmp_path, mutations={"site.css": b"\x80bad-utf8"})

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_sanitized_error(excinfo, "SITE_FILE_UTF8", expect_suppressed_context=True)


def test_renderer_rejects_malformed_allowlist_json_without_path_leak(tmp_path: Path) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    site_root = _make_site_copy(tmp_path, mutations={"links.allowlist.json": "{not-json"})

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_sanitized_error(excinfo, "ALLOWLIST_JSON", expect_suppressed_context=True)


def test_renderer_reads_only_the_five_authorized_site_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _render_module()
    ledger: list[Path] = []
    original_read_bytes = Path.read_bytes

    def ledgered_read_bytes(path: Path) -> bytes:
        if path.parent == SITE_ROOT:
            ledger.append(path)
        return original_read_bytes(path)

    monkeypatch.setattr(module.Path, "read_bytes", ledgered_read_bytes)

    _render()

    assert set(ledger) == {SITE_ROOT / filename for filename in AUTHORIZED_SITE_FILES}
    assert len(ledger) == len(AUTHORIZED_SITE_FILES)


def test_renderer_escapes_hostile_dynamic_scalars_without_emitting_markup() -> None:
    _error_type, escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)

    injected_values = {
        "tag_name": 'v0.2.2"><script data-tag="1">',
        "tag_object": 'tag-object"><svg data-tag-object="1">',
        "peeled_commit": 'peeled"><img data-peel="1">',
        "readme_blob": 'readme"><math data-readme="1">',
        "data_card_blob": 'data-card"><details data-card="1">',
        "model_card_blob": 'model-card"><iframe data-model="1">',
        "svg_blob": 'svg-blob"><style data-svg="1">',
        "loss": 'loss"><script data-loss="1">',
        "public_filename": 'model"><script data-file="1"></script>.svg',
    }
    mutated_provenance = replace(
        evidence.provenance,
        tag_name=injected_values["tag_name"],
        tag_object=injected_values["tag_object"],
        peeled_commit=injected_values["peeled_commit"],
        readme_blob=injected_values["readme_blob"],
        data_card_blob=injected_values["data_card_blob"],
        model_card_blob=injected_values["model_card_blob"],
        svg_blob=injected_values["svg_blob"],
    )
    mutated_rows = (
        replace(evidence.rows[0], loss=injected_values["loss"]),
        evidence.rows[1],
    )
    mutated_evidence = replace(
        evidence,
        provenance=mutated_provenance,
        rows=mutated_rows,
        validation_images=321,
        bootstrap_iterations=4567,
    )
    mutated_svg = replace(verified_svg, public_filename=injected_values["public_filename"])
    rendered = render_site(
        evidence=mutated_evidence,
        verified_svg=mutated_svg,
        site_source_sha="b" * 40,
        site_root=SITE_ROOT,
    )
    text = rendered.index_html.decode("utf-8")

    assert "<script" not in text.casefold()
    assert "321 張 Official Validation" in text
    assert "4,567 次 image-level percentile Bootstrap" in text
    assert "site source SHA: <code>bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb</code>" in text
    assert escape_text(injected_values["tag_name"]) in text
    assert escape_text(injected_values["tag_object"]) in text
    assert escape_text(injected_values["peeled_commit"]) in text
    assert escape_text(injected_values["readme_blob"]) in text
    assert escape_text(injected_values["data_card_blob"]) in text
    assert escape_text(injected_values["model_card_blob"]) in text
    assert escape_text(injected_values["svg_blob"]) in text
    assert escape_text(injected_values["loss"]) in text
    assert escape_text(f"/WoundScope/assets/{injected_values['public_filename']}") in text
    for raw_value in injected_values.values():
        assert raw_value not in text


@pytest.mark.parametrize(
    ("filename", "mutated_text", "expected_code"),
    [
        (
            "index.template.html",
            (
                (SITE_ROOT / "index.template.html")
                .read_text("utf-8")
                .replace("{{VALIDATION_IMAGES}}", "{{VALIDATION_IMAGES}}{{VALIDATION_IMAGES}}", 1)
            ),
            "TEMPLATE_SLOT_DUPLICATE",
        ),
        (
            "index.template.html",
            (SITE_ROOT / "index.template.html")
            .read_text("utf-8")
            .replace("{{VALIDATION_IMAGES}}", "{{BROKEN_SLOT}}", 1),
            "TEMPLATE_SLOT_MISSING",
        ),
        (
            "index.template.html",
            (SITE_ROOT / "index.template.html")
            .read_text("utf-8")
            .replace("{{README_BLOB}}", "README_BLOB", 1),
            "TEMPLATE_SLOT_UNKNOWN",
        ),
    ],
)
def test_template_slot_failures_are_fail_closed(
    tmp_path: Path,
    filename: str,
    mutated_text: str,
    expected_code: str,
) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    site_root = _make_site_copy(tmp_path, mutations={filename: mutated_text})

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_public_error(excinfo, expected_code)


def _mutated_allowlist(first_url: str) -> str:
    allowlist = json.loads((SITE_ROOT / "links.allowlist.json").read_text("utf-8"))
    allowlist[0] = first_url
    return json.dumps(allowlist, ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize(
    ("mutated_url", "expected_code"),
    [
        ("https://doi.org/10.1038/s41598-020-78799-w#frag", "ALLOWLIST_QUERY_OR_FRAGMENT"),
        ("https://doi.org/10.1038/s41598-020-78799-w?x=1", "ALLOWLIST_QUERY_OR_FRAGMENT"),
        ("https://bit.ly/woundscope", "ALLOWLIST_SHORTENER"),
        ("mailto:test@example.com", "ALLOWLIST_SCHEME"),
        ("data:text/plain,hi", "ALLOWLIST_SCHEME"),
        ("javascript:alert(1)", "ALLOWLIST_SCHEME"),
        (
            "https://example.com/redirect/https://doi.org/10.1038/s41598-020-78799-w",
            "ALLOWLIST_MISMATCH",
        ),
    ],
)
def test_allowlist_mutations_fail_closed(
    tmp_path: Path,
    mutated_url: str,
    expected_code: str,
) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    site_root = _make_site_copy(
        tmp_path,
        mutations={"links.allowlist.json": _mutated_allowlist(mutated_url)},
    )

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_public_error(excinfo, expected_code)


def test_rendered_notices_match_exact_required_payload() -> None:
    rendered = _render()

    assert rendered.notices == _lf_bytes(EXPECTED_NOTICES_TEXT)


def test_renderer_rejects_notice_content_drift(tmp_path: Path) -> None:
    error_type, _escape_text, render_site = _render_exports()
    load_public_evidence, load_verified_svg = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    site_root = _make_site_copy(
        tmp_path,
        mutations={
            "THIRD_PARTY_NOTICES.txt": EXPECTED_NOTICES_TEXT.replace(
                "packages: none.", "packages: one.", 1
            )
        },
    )

    with pytest.raises(error_type) as excinfo:
        render_site(evidence, verified_svg, "a" * 40, site_root)

    _assert_public_error(excinfo, "NOTICE_CONTENT")


def test_rendered_pages_include_theme_color_meta_and_lazy_aggregate_image() -> None:
    rendered = _render()
    index_structure = _parse_structure(rendered.index_html)
    not_found_structure = _parse_structure(rendered.not_found_html)

    assert tuple(index_structure.theme_colors) == EXPECTED_THEME_COLORS
    assert tuple(not_found_structure.theme_colors) == EXPECTED_THEME_COLORS
    assert len(index_structure.img_attrs) == 1
    aggregate_image = index_structure.img_attrs[0]
    assert aggregate_image["loading"] == "lazy"
    assert aggregate_image["width"] == "1200"
    assert aggregate_image["height"] == "520"
