"""Build and audit the deterministic WoundScope Pages publish tree."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from .constants import (
    AUTHORED_SITE_FILES,
    BASE_PATH,
    CLAIM_BOUNDARY_VERSION,
    DATA_CARD_BLOB,
    EXPECTED_BROWSER_REVISIONS,
    EXPECTED_CSP,
    EXPECTED_LICENSE_LENGTH,
    EXPECTED_LICENSE_SHA256,
    EXPECTED_PUBLIC_SVG_FILENAME,
    EXPECTED_PUBLIC_SVG_LENGTH,
    EXPECTED_PUBLIC_SVG_SHA256,
    EXTERNAL_LINK_ALLOWLIST,
    FORBIDDEN_METRIC_LITERALS,
    LICENSE_BLOB,
    LICENSE_PATH,
    MANUAL_BROWSER_ZOOM_FIELD,
    MAX_CSS_BYTES,
    MAX_TOTAL_PUBLISH_BYTES,
    MODEL_CARD_BLOB,
    NETWORK_CONTRACT_VERSION,
    PUBLISH_FILE_BUDGETS,
    README_BLOB,
    REVIEW_REPORT_FILES,
    REVIEW_SCREENSHOT_DIRECTORY,
    REVIEW_SCREENSHOT_SUFFIX,
    SITE_BUILD_MODE,
    SVG_BLOB,
    TAG_NAME,
    TAG_OBJECT,
)
from .evidence import PEELED_COMMIT, PublicEvidence, load_public_evidence
from .render import render_site
from .svg_contract import load_verified_svg

_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_APPROVAL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_STYLE_HREF_RE = re.compile(r'href="/WoundScope/site\.css"')
_CSP_RE = re.compile(r'(<meta http-equiv="Content-Security-Policy" content=")([^"]+)(">)')
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
_REPORTED_OWNER = "kuotunyu"
_SITE_SOURCE_FOOTER_RE = re.compile(
    r"site source SHA:\s*<code>(?P<site_source>[0-9a-f]{40})</code>\s*·\s*tag object:\s*"
    r"<code>(?P<tag_object>[0-9a-f]{40})</code>\s*·\s*peeled commit:\s*"
    r"<code>(?P<peeled_commit>[0-9a-f]{40})</code>"
)
_HTML_ALLOWED_ATTRIBUTES = {
    "a": frozenset({"class", "href", "rel", "target"}),
    "body": frozenset(),
    "caption": frozenset({"id"}),
    "circle": frozenset({"cx", "cy", "r"}),
    "code": frozenset(),
    "div": frozenset({"aria-labelledby", "class", "role", "tabindex"}),
    "figcaption": frozenset({"class"}),
    "figure": frozenset({"class"}),
    "footer": frozenset({"class"}),
    "h1": frozenset({"id"}),
    "h2": frozenset({"id"}),
    "h3": frozenset(),
    "head": frozenset(),
    "header": frozenset({"class"}),
    "html": frozenset({"lang"}),
    "img": frozenset({"alt", "height", "loading", "src", "width"}),
    "li": frozenset(),
    "link": frozenset({"href", "rel"}),
    "main": frozenset({"class", "id", "tabindex"}),
    "meta": frozenset({"charset", "content", "http-equiv", "media", "name"}),
    "nav": frozenset({"aria-label"}),
    "p": frozenset({"class", "id"}),
    "path": frozenset({"d", "fill", "stroke", "stroke-width"}),
    "section": frozenset({"aria-labelledby", "class", "id"}),
    "span": frozenset(),
    "svg": frozenset({"aria-hidden", "focusable", "viewbox"}),
    "table": frozenset({"aria-describedby"}),
    "tbody": frozenset(),
    "td": frozenset(),
    "th": frozenset({"scope"}),
    "thead": frozenset(),
    "title": frozenset(),
    "tr": frozenset(),
    "ul": frozenset({"class"}),
}
_HTML_URL_ATTRIBUTES = frozenset(
    {
        "action",
        "cite",
        "data",
        "formaction",
        "href",
        "poster",
        "src",
        "srcset",
    }
)
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_ESCAPE_RE = re.compile(r"\\([0-9a-fA-F]{1,6})(?:\r\n|[ \t\r\n\f])?|\\(.)", re.DOTALL)
_TABLE_FOCUS_REGION_ATTRIBUTES = tuple(
    sorted(
        {
            "aria-labelledby": "evidence-table-caption",
            "class": "table-scroll",
            "role": "region",
            "tabindex": "0",
        }.items()
    )
)
_TABLE_CAPTION_ATTRIBUTES = tuple(sorted({"id": "evidence-table-caption"}.items()))
_VOID_HTML_TAGS = frozenset({"img", "link", "meta"})
_DOCUMENT_HTML_ATTRIBUTES = tuple(sorted({"lang": "zh-Hant-TW"}.items()))
_HEAD_ONLY_TAGS = frozenset({"link", "meta", "title"})


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


def _canonical_rel_tokens(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(sorted(token for token in value.split() if token))


def _meta_record(**attrs: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    return ("meta", tuple(sorted(attrs.items())))


def _url_record(tag: str, **attrs: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (tag, tuple(sorted(attrs.items())))


def _expected_main_records(
    public_path: str,
) -> Counter[tuple[tuple[str, str], ...]]:
    if public_path == "index.html":
        return Counter({tuple(sorted({"id": "main-content", "tabindex": "-1"}.items())): 1})
    if public_path == "404.html":
        return Counter({tuple(sorted({"class": "not-found", "id": "main-content"}.items())): 1})
    raise PagesAuditError("HTML_MAIN_MISMATCH", public_path=public_path)


def _expected_title(public_path: str) -> str:
    if public_path == "index.html":
        return "WoundScope | 靜態研究成果展示"
    if public_path == "404.html":
        return "WoundScope | 找不到此頁面"
    raise PagesAuditError("HTML_TITLE_MISMATCH", public_path=public_path)


def _expected_focus_region_records(
    public_path: str,
) -> Counter[tuple[tuple[str, str], ...]]:
    if public_path == "index.html":
        return Counter({_TABLE_FOCUS_REGION_ATTRIBUTES: 1})
    if public_path == "404.html":
        return Counter()
    raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)


def _expected_tabindex_records(
    public_path: str,
) -> Counter[tuple[str, tuple[tuple[str, str], ...]]]:
    if public_path == "index.html":
        return Counter(
            {
                (
                    "main",
                    tuple(sorted({"id": "main-content", "tabindex": "-1"}.items())),
                ): 1,
                ("div", _TABLE_FOCUS_REGION_ATTRIBUTES): 1,
            }
        )
    if public_path == "404.html":
        return Counter()
    raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)


def _expected_meta_records(
    public_path: str,
) -> Counter[tuple[str, tuple[tuple[str, str], ...]]]:
    records = Counter(
        {
            _meta_record(charset="utf-8"): 1,
            _meta_record(name="viewport", content="width=device-width, initial-scale=1"): 1,
            _meta_record(
                name="theme-color",
                media="(prefers-color-scheme: light)",
                content="#f4f0e8",
            ): 1,
            _meta_record(
                name="theme-color",
                media="(prefers-color-scheme: dark)",
                content="#151310",
            ): 1,
        }
    )
    if public_path == "index.html":
        records.update(
            {
                _meta_record(
                    name="description",
                    content="WoundScope 足部潰瘍二元語意分割的靜態研究成果展示。",
                ): 1,
                _meta_record(
                    name="woundscope:candidate-canonical-url",
                    content="https://kuotunyu.github.io/WoundScope/",
                ): 1,
                _meta_record(
                    **{"http-equiv": "Content-Security-Policy", "content": EXPECTED_CSP}
                ): 1,
            }
        )
        return records
    if public_path == "404.html":
        records.update(
            {
                _meta_record(
                    name="description",
                    content="WoundScope 靜態研究成果展示頁面。",
                ): 1,
                _meta_record(
                    **{"http-equiv": "Content-Security-Policy", "content": EXPECTED_CSP}
                ): 1,
            }
        )
        return records
    raise PagesAuditError("HTML_META_MISMATCH", public_path=public_path)


def _expected_url_records(
    public_path: str, *, css_relative: str, svg_relative: str
) -> Counter[tuple[str, tuple[tuple[str, str], ...]]]:
    stylesheet_href = f"{BASE_PATH}{css_relative}"
    if public_path == "index.html":
        records = Counter(
            {
                _url_record("link", href=stylesheet_href, rel="stylesheet"): 1,
                _url_record("a", href="#main-content"): 1,
                _url_record("a", href="#overview"): 1,
                _url_record("a", href="#evidence"): 1,
                _url_record("a", href="#provenance"): 1,
                _url_record(
                    "img",
                    src=f"{BASE_PATH}{svg_relative}",
                    alt="鎖定 Official Validation 的彙總 SVG，比較 EfficientNet-B0 U-Net 與 "
                    "SegFormer-B0 的 Dice 與 IoU。",
                    width="1200",
                    height="520",
                    loading="lazy",
                ): 1,
            }
        )
        for href in EXTERNAL_LINK_ALLOWLIST:
            records.update(
                {
                    _url_record(
                        "a",
                        href=href,
                        rel="noopener noreferrer",
                        target="_blank",
                    ): 1
                }
            )
        return records
    if public_path == "404.html":
        return Counter(
            {
                _url_record("link", href=stylesheet_href, rel="stylesheet"): 1,
                _url_record("a", href=BASE_PATH): 1,
            }
        )
    raise PagesAuditError("HTML_WIRING_MISMATCH", public_path=public_path)


class _HtmlAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.external_anchors: list[_Anchor] = []
        self.csp_values: list[str] = []
        self.internal_references: list[tuple[str, str]] = []
        self.invalid_attributes: list[str] = []
        self.invalid_external_resources: list[str] = []
        self.invalid_structure: list[str] = []
        self.invalid_tags: list[str] = []
        self.main_records: Counter[tuple[tuple[str, str], ...]] = Counter()
        self.meta_records: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
        self.url_records: Counter[tuple[str, tuple[tuple[str, str], ...]]] = Counter()
        self.focus_region_records: list[
            tuple[int, tuple[tuple[str, str], ...]]
        ] = []
        self.tabindex_records: Counter[
            tuple[str, tuple[tuple[str, str], ...]]
        ] = Counter()
        self.table_records: list[tuple[int, int | None]] = []
        self.caption_records: list[
            tuple[int, tuple[tuple[str, str], ...], int | None, int | None]
        ] = []
        self.caption_text: dict[int, list[str]] = {}
        self.title_records: list[int] = []
        self.title_text: dict[int, list[str]] = {}
        self.invalid_title_content: list[str] = []
        self.id_records: Counter[str] = Counter()
        self.doctype_records: list[str] = []
        self.html_records: Counter[tuple[tuple[str, str], ...]] = Counter()
        self.html_child_tags: list[str] = []
        self._next_element_id = 0
        self._open_elements: list[tuple[int, str, dict[str, str]]] = []
        self._root_started = False
        self._root_closed = False

    def _nearest_open_element(self, tag: str) -> int | None:
        for element_id, open_tag, _attrs in reversed(self._open_elements):
            if open_tag == tag:
                return element_id
        return None

    def _nearest_table_region(self) -> int | None:
        for element_id, tag, attrs in reversed(self._open_elements):
            if tag == "div" and attrs.get("class") == "table-scroll":
                return element_id
        return None

    def _has_open_element(self, tag: str) -> bool:
        return any(open_tag == tag for _element_id, open_tag, _attrs in self._open_elements)

    def _record_document_start(
        self, tag: str, attribute_record: tuple[tuple[str, str], ...]
    ) -> None:
        parent_tag = self._open_elements[-1][1] if self._open_elements else None
        if tag == "html":
            self.html_records.update({attribute_record: 1})
            if (
                parent_tag is not None
                or self._root_started
                or self._root_closed
                or self.doctype_records != ["doctype html"]
            ):
                self.invalid_structure.append("html-root")
            self._root_started = True
            return
        if not self._root_started or self._root_closed:
            self.invalid_structure.append(f"outside-root:{tag}")
        if parent_tag == "html":
            self.html_child_tags.append(tag)
        if tag in {"head", "body"} and parent_tag != "html":
            self.invalid_structure.append(f"wrapper-parent:{tag}")
        if tag in _HEAD_ONLY_TAGS and parent_tag != "head":
            self.invalid_structure.append(f"head-context:{tag}")
        if tag not in {"body", "head", "html", *_HEAD_ONLY_TAGS} and not self._has_open_element(
            "body"
        ):
            self.invalid_structure.append(f"body-context:{tag}")

    def has_valid_document_skeleton(self) -> bool:
        return (
            self.doctype_records == ["doctype html"]
            and self.html_records == Counter({_DOCUMENT_HTML_ATTRIBUTES: 1})
            and self.html_child_tags == ["head", "body"]
            and self._root_started
            and self._root_closed
        )

    def _record_title_non_data(self, callback: str) -> bool:
        title_is_open = self._nearest_open_element("title") is not None
        if title_is_open:
            self.invalid_title_content.append(callback)
        return title_is_open

    def handle_comment(self, data: str) -> None:
        self._record_title_non_data("comment")

    def handle_pi(self, data: str) -> None:
        self._record_title_non_data("processing-instruction")

    def unknown_decl(self, data: str) -> None:
        self._record_title_non_data("unknown-declaration")

    def handle_decl(self, decl: str) -> None:
        if self._record_title_non_data("declaration"):
            return
        self.doctype_records.append(decl)
        if (
            decl != "doctype html"
            or len(self.doctype_records) != 1
            or self._open_elements
            or self._root_started
            or self._root_closed
        ):
            self.invalid_structure.append("doctype")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _HTML_ALLOWED_ATTRIBUTES:
            self.invalid_tags.append(tag)
            return
        seen_attributes: set[str] = set()
        for name, _value in attrs:
            normalized_name = name.casefold()
            if normalized_name in seen_attributes:
                self.invalid_attributes.append(f"{tag}[{normalized_name}]")
                return
            seen_attributes.add(normalized_name)
        attr_map = {name: value or "" for name, value in attrs}
        element_id = self._next_element_id
        self._next_element_id += 1
        if any(name.startswith("on") for name, _value in attrs):
            self.invalid_attributes.append(tag)
        for forbidden_attr in ("style", "contenteditable", "download"):
            if forbidden_attr in attr_map:
                self.invalid_attributes.append(f"{tag}[{forbidden_attr}]")
        for name, _value in attrs:
            if name not in _HTML_ALLOWED_ATTRIBUTES[tag]:
                self.invalid_attributes.append(f"{tag}[{name}]")
        if tag == "main":
            self.main_records.update({tuple(sorted(attr_map.items())): 1})
        attribute_record = tuple(sorted(attr_map.items()))
        self._record_document_start(tag, attribute_record)
        if "id" in attr_map:
            self.id_records.update({attr_map["id"]: 1})
        if "tabindex" in attr_map:
            self.tabindex_records.update({(tag, attribute_record): 1})
        if tag == "div" and (
            attr_map.get("class") == "table-scroll"
            or any(name in attr_map for name in ("aria-labelledby", "role", "tabindex"))
        ):
            self.focus_region_records.append((element_id, attribute_record))
        if tag == "table":
            self.table_records.append((element_id, self._nearest_table_region()))
        if tag == "caption":
            self.caption_records.append(
                (
                    element_id,
                    attribute_record,
                    self._nearest_open_element("table"),
                    self._nearest_table_region(),
                )
            )
            self.caption_text[element_id] = []
        if tag == "title":
            self.title_records.append(element_id)
            self.title_text[element_id] = []
        if tag == "meta":
            self.meta_records.update(
                {
                    _meta_record(
                        **{
                            key: value
                            for key, value in attr_map.items()
                            if key in {"charset", "content", "http-equiv", "media", "name"}
                        }
                    ): 1
                }
            )
        if tag == "meta" and attr_map.get("http-equiv") == "Content-Security-Policy":
            content = attr_map.get("content")
            if content is not None:
                self.csp_values.append(content)
        if tag == "link" and (attr_map.get("rel") or "").casefold() != "stylesheet":
            self.invalid_external_resources.append("link[rel]")
        if tag == "a" and "href" in attr_map:
            href = attr_map["href"]
            rel_tokens = _canonical_rel_tokens(attr_map.get("rel"))
            target = attr_map.get("target")
            self.url_records.update(
                {
                    _url_record(
                        "a",
                        href=href,
                        **({"rel": " ".join(rel_tokens)} if rel_tokens else {}),
                        **({"target": target} if target else {}),
                    ): 1
                }
            )
            if href.startswith("https://"):
                self.external_anchors.append(
                    _Anchor(href=href, rel=frozenset(rel_tokens), target=target or None)
                )
            else:
                self.internal_references.append((tag, href))
        elif tag == "img" and "src" in attr_map:
            src = attr_map["src"]
            self.url_records.update(
                {
                    _url_record(
                        "img",
                        src=src,
                        **{
                            key: value
                            for key, value in attr_map.items()
                            if key in {"alt", "height", "loading", "width"}
                        },
                    ): 1
                }
            )
            self.internal_references.append((tag, src))
        elif tag == "link" and "href" in attr_map:
            href = attr_map["href"]
            rel_tokens = _canonical_rel_tokens(attr_map.get("rel"))
            self.url_records.update(
                {
                    _url_record(
                        "link",
                        href=href,
                        **({"rel": " ".join(rel_tokens)} if rel_tokens else {}),
                    ): 1
                }
            )
            self.internal_references.append((tag, href))
        for name in _HTML_URL_ATTRIBUTES:
            if name in attr_map and not (
                (tag == "a" and name == "href")
                or (tag == "img" and name == "src")
                or (tag == "link" and name == "href")
            ):
                self.invalid_external_resources.append(f"{tag}[{name}]")
        if tag not in _VOID_HTML_TAGS:
            self._open_elements.append((element_id, tag, attr_map))

    def handle_data(self, data: str) -> None:
        if data.strip() and (not self._open_elements or self._open_elements[-1][1] == "html"):
            self.invalid_structure.append("root-text")
        caption_id = self._nearest_open_element("caption")
        if caption_id is not None:
            self.caption_text[caption_id].append(data)
        title_id = self._nearest_open_element("title")
        if title_id is not None:
            self.title_text[title_id].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_HTML_TAGS:
            self.invalid_structure.append(f"void-close:{tag}")
            return
        if not self._open_elements or self._open_elements[-1][1] != tag:
            self.invalid_structure.append(f"unexpected-close:{tag}")
            return
        self._open_elements.pop()
        if tag == "html":
            self._root_closed = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        original_depth = len(self._open_elements)
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_HTML_TAGS:
            self.invalid_structure.append(f"nonvoid-startend:{tag}")
            if len(self._open_elements) > original_depth:
                self._open_elements.pop()

    def close(self) -> None:
        super().close()
        if self._open_elements:
            self.invalid_structure.append("unclosed-eof")


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


def _absolute_lexical_path(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _existing_lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _validate_path_components(path: Path, *, code: str, public_path: str) -> Path:
    if any(part == ".." for part in path.parts):
        raise PagesAuditError(code, public_path=public_path)
    anchored = _absolute_lexical_path(path)
    current: Path | None = None
    for index, part in enumerate(anchored.parts):
        current = Path(part) if index == 0 else current / part
        current_stat = _existing_lstat(current)
        if current_stat is None:
            return anchored
        if stat.S_ISLNK(current_stat.st_mode) or _is_reparse_point(current_stat):
            raise PagesAuditError(code, public_path=public_path)
        if index < len(anchored.parts) - 1 and not stat.S_ISDIR(current_stat.st_mode):
            raise PagesAuditError(code, public_path=public_path)
    return anchored


def _require_existing_directory(
    path: Path,
    *,
    missing_code: str,
    unsafe_code: str,
    special_code: str,
    public_path: str,
) -> Path:
    anchored = _validate_path_components(path, code=unsafe_code, public_path=public_path)
    path_stat = _existing_lstat(anchored)
    if path_stat is None:
        raise PagesAuditError(missing_code, public_path=public_path)
    if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
        raise PagesAuditError(unsafe_code, public_path=public_path)
    if not stat.S_ISDIR(path_stat.st_mode):
        raise PagesAuditError(special_code, public_path=public_path)
    return anchored


def _require_existing_regular_file(path: Path, *, code: str, public_path: str) -> Path:
    anchored = _validate_path_components(path, code=code, public_path=public_path)
    path_stat = _existing_lstat(anchored)
    if path_stat is None or stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
        raise PagesAuditError(code, public_path=public_path)
    if not stat.S_ISREG(path_stat.st_mode):
        raise PagesAuditError(code, public_path=public_path)
    return anchored


def _ensure_safe_directory(path: Path, *, code: str, public_path: str) -> Path:
    anchored = _validate_path_components(path, code=code, public_path=public_path)
    path_stat = _existing_lstat(anchored)
    if path_stat is None:
        anchored.mkdir(parents=True, exist_ok=True)
        path_stat = anchored.lstat()
    if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
        raise PagesAuditError(code, public_path=public_path)
    if not stat.S_ISDIR(path_stat.st_mode):
        raise PagesAuditError(code, public_path=public_path)
    return anchored


def _prepare_output_directory(path: Path, *, public_path: str) -> tuple[Path, bool]:
    anchored = _validate_path_components(path, code="OUTPUT_PATH_UNSAFE", public_path=public_path)
    path_stat = _existing_lstat(anchored)
    if path_stat is None:
        return anchored, False
    if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
        raise PagesAuditError("OUTPUT_PATH_UNSAFE", public_path=public_path)
    if not stat.S_ISDIR(path_stat.st_mode):
        raise PagesAuditError("OUTPUT_EXISTS", public_path=public_path)
    if any(anchored.iterdir()):
        raise PagesAuditError("OUTPUT_EXISTS", public_path=public_path)
    return anchored, True


def _write_bytes_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)
    path_stat = path.lstat()
    if (
        stat.S_ISLNK(path_stat.st_mode)
        or _is_reparse_point(path_stat)
        or not stat.S_ISREG(path_stat.st_mode)
    ):
        raise PagesAuditError("OUTPUT_PATH_UNSAFE", public_path=path.name)
    if path_stat.st_size != len(payload) or _sha256_path(path) != _sha256_bytes(payload):
        raise PagesAuditError("OUTPUT_WRITE_MISMATCH", public_path=path.name)


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


def _git_tree_blob_id(repository: Path, commit_sha: str, public_path: str) -> str:
    entry = _run_git_text(
        repository, ["ls-tree", commit_sha, "--", public_path], code="SITE_SOURCE_READ"
    )
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


def _toolchain_payload(repository: Path | None = None) -> dict[str, str]:
    try:
        completed = subprocess.run(
            ["git", "--version"],
            cwd=repository,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as error:
        raise PagesAuditError("GIT_COMMAND_FAILED") from error
    return {
        "git": completed.stdout.decode("utf-8").strip(),
        "python": sys.version.split()[0],
    }


def _expected_manifest_evidence_payload() -> dict[str, str]:
    return {
        "data_card_blob": DATA_CARD_BLOB,
        "model_card_blob": MODEL_CARD_BLOB,
        "peeled_commit": PEELED_COMMIT,
        "readme_blob": README_BLOB,
        "svg_blob": SVG_BLOB,
        "tag_name": TAG_NAME,
        "tag_object": TAG_OBJECT,
    }


def _file_payloads(file_records: tuple[_FileRecord, ...]) -> list[dict[str, object]]:
    return [
        {"bytes": record.bytes_size, "path": record.path, "sha256": record.sha256}
        for record in sorted(file_records, key=lambda item: item.path.encode("utf-8"))
    ]


def _expected_manifest_payload(
    site_source_sha: str,
    source_date_epoch: int,
    file_records: tuple[_FileRecord, ...],
    publish_tree_sha256: str,
    *,
    repository: Path | None,
) -> dict[str, object]:
    return {
        "base_path": BASE_PATH,
        "build_mode": SITE_BUILD_MODE,
        "claim_boundary_version": CLAIM_BOUNDARY_VERSION,
        "evidence": _expected_manifest_evidence_payload(),
        "files": _file_payloads(file_records),
        "network_contract_version": NETWORK_CONTRACT_VERSION,
        "publish_tree_sha256": publish_tree_sha256,
        "site_source_sha": site_source_sha,
        "source_date_epoch": source_date_epoch,
        "toolchain": _toolchain_payload(repository),
    }


def _spdx_file_id(relative_path: str) -> str:
    return "SPDXRef-File-" + re.sub(r"[^A-Za-z0-9]+", "-", relative_path).strip("-")


def _spdx_payload(
    site_source_sha: str,
    source_date_epoch: int,
    file_records: tuple[_FileRecord, ...],
) -> bytes:
    return _json_bytes(_expected_spdx_payload(site_source_sha, source_date_epoch, file_records))


def _expected_spdx_payload(
    site_source_sha: str,
    source_date_epoch: int,
    file_records: tuple[_FileRecord, ...],
) -> dict[str, object]:
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
                "copyrightText": "NOASSERTION",
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
    return {
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
                "copyrightText": "NOASSERTION",
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


def _manifest_payload(
    site_source_sha: str,
    evidence: PublicEvidence,
    source_date_epoch: int,
    file_records: tuple[_FileRecord, ...],
    publish_tree_sha256: str,
    *,
    repository: Path,
) -> bytes:
    payload = _expected_manifest_payload(
        site_source_sha,
        source_date_epoch,
        file_records,
        publish_tree_sha256,
        repository=repository,
    )
    if payload["evidence"] != {
        "data_card_blob": evidence.provenance.data_card_blob,
        "model_card_blob": evidence.provenance.model_card_blob,
        "peeled_commit": evidence.provenance.peeled_commit,
        "readme_blob": evidence.provenance.readme_blob,
        "svg_blob": evidence.provenance.svg_blob,
        "tag_name": evidence.provenance.tag_name,
        "tag_object": evidence.provenance.tag_object,
    }:
        raise PagesAuditError("MANIFEST_STRUCTURE", public_path="pages-manifest.json")
    return _json_bytes(payload)


def _classify_extra_path(relative_path: str) -> str:
    lower = relative_path.casefold()
    suffix = Path(relative_path).suffix.casefold()
    if (
        lower == "data"
        or lower.startswith("data/")
        or lower == "artifacts"
        or lower.startswith("artifacts/")
    ):
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
    publish = _require_existing_directory(
        publish,
        missing_code="TREE_MISSING_FILE",
        unsafe_code="TREE_SYMLINK",
        special_code="TREE_SPECIAL_FILE",
        public_path=".",
    )
    css_relative: str | None = None
    svg_relative: str | None = None
    for path in publish.rglob("*"):
        relative_path = path.relative_to(publish).as_posix()
        stats = path.lstat()
        if stat.S_ISLNK(stats.st_mode) or _is_reparse_point(stats):
            raise PagesAuditError("TREE_SYMLINK", public_path=relative_path)
        if stat.S_ISDIR(stats.st_mode):
            if relative_path == "assets":
                continue
            raise PagesAuditError(_classify_extra_path(relative_path), public_path=relative_path)
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


def _validate_internal_reference(tag: str, value: str, *, public_path: str) -> None:
    if value.startswith("//"):
        raise PagesAuditError(
            "HTML_EXTERNAL_LINK" if tag == "a" else "HTML_EXTERNAL_RESOURCE",
            public_path=public_path,
        )
    if re.match(r"(?i)[a-z][a-z0-9+.-]*:", value):
        raise PagesAuditError(
            "HTML_EXTERNAL_LINK" if tag == "a" else "HTML_EXTERNAL_RESOURCE",
            public_path=public_path,
        )
    if tag == "a":
        if value.startswith("#"):
            return
        if value.startswith(BASE_PATH):
            return
        if value.startswith("/"):
            raise PagesAuditError("HTML_SUBPATH", public_path=public_path)
        raise PagesAuditError("HTML_EXTERNAL_LINK", public_path=public_path)
    if tag in {"img", "link"}:
        if value.startswith(BASE_PATH):
            return
        if value.startswith("/"):
            raise PagesAuditError("HTML_SUBPATH", public_path=public_path)
        raise PagesAuditError("HTML_EXTERNAL_RESOURCE", public_path=public_path)
    raise PagesAuditError("HTML_EXTERNAL_RESOURCE", public_path=public_path)


def _validate_focus_region_contract(
    parser: _HtmlAuditParser,
    *,
    public_path: str,
) -> None:
    focus_region_attributes = Counter(
        attributes for _element_id, attributes in parser.focus_region_records
    )
    if focus_region_attributes != _expected_focus_region_records(public_path):
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)
    if parser.tabindex_records != _expected_tabindex_records(public_path):
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)

    caption_attributes = Counter(
        attributes
        for _element_id, attributes, _table_id, _region_id in parser.caption_records
    )
    if public_path == "404.html":
        if caption_attributes:
            raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)
        return
    if public_path != "index.html":
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)
    if caption_attributes != Counter({_TABLE_CAPTION_ATTRIBUTES: 1}):
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)
    if parser.id_records["evidence-table-caption"] != 1:
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)
    if len(parser.focus_region_records) != 1 or len(parser.table_records) != 1:
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)

    region_id, _region_attributes = parser.focus_region_records[0]
    table_id, table_region_id = parser.table_records[0]
    caption_id, _caption_attributes, caption_table_id, caption_region_id = (
        parser.caption_records[0]
    )
    if (
        table_region_id != region_id
        or caption_table_id != table_id
        or caption_region_id != region_id
        or not "".join(parser.caption_text[caption_id]).strip()
    ):
        raise PagesAuditError("HTML_FOCUS_REGION_MISMATCH", public_path=public_path)


def _verify_html(
    path: Path,
    public_path: str,
    *,
    css_relative: str,
    svg_relative: str,
) -> None:
    if path.stat().st_size > PUBLISH_FILE_BUDGETS[public_path]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path=public_path)
    text = _decode_utf8(path, public_path)
    _assert_no_path_or_secret_leak(text, public_path)
    parser = _HtmlAuditParser()
    parser.feed(text)
    parser.close()
    if parser.invalid_tags:
        raise PagesAuditError("HTML_TAG_INVALID", public_path=public_path)
    if parser.invalid_attributes:
        raise PagesAuditError("HTML_ATTRIBUTE_INVALID", public_path=public_path)
    if parser.invalid_structure or not parser.has_valid_document_skeleton():
        raise PagesAuditError("HTML_STRUCTURE_INVALID", public_path=public_path)
    decoded_titles = ["".join(parser.title_text[title_id]) for title_id in parser.title_records]
    if parser.invalid_title_content or decoded_titles != [_expected_title(public_path)]:
        raise PagesAuditError("HTML_TITLE_MISMATCH", public_path=public_path)
    if parser.main_records != _expected_main_records(public_path):
        raise PagesAuditError("HTML_MAIN_MISMATCH", public_path=public_path)
    _validate_focus_region_contract(parser, public_path=public_path)
    if parser.invalid_external_resources:
        raise PagesAuditError("HTML_EXTERNAL_RESOURCE", public_path=public_path)
    expected_meta = _expected_meta_records(public_path)
    expected_csp_record = _meta_record(
        **{"http-equiv": "Content-Security-Policy", "content": EXPECTED_CSP}
    )
    if parser.meta_records != expected_meta:
        actual_csp_records = [
            record
            for record, count in parser.meta_records.items()
            for _ in range(count)
            if any(key == "http-equiv" for key, _value in record[1])
        ]
        if (
            expected_meta[expected_csp_record] == 1
            and parser.meta_records.get(expected_csp_record, 0) == 0
            and len(actual_csp_records) == 1
            and parser.csp_values == []
        ):
            raise PagesAuditError("HTML_CSP_MISMATCH", public_path=public_path)
        if (
            expected_meta[expected_csp_record] == 1
            and parser.meta_records.get(expected_csp_record, 0) == 0
            and len(actual_csp_records) == 1
            and parser.csp_values != [EXPECTED_CSP]
            and actual_csp_records[0][1]
            != tuple(
                sorted({"http-equiv": "Content-Security-Policy", "content": EXPECTED_CSP}.items())
            )
        ):
            raise PagesAuditError("HTML_CSP_MISMATCH", public_path=public_path)
        raise PagesAuditError("HTML_META_MISMATCH", public_path=public_path)
    if _RUNTIME_JS_RE.search(text):
        raise PagesAuditError("TREE_JAVASCRIPT", public_path=public_path)
    if _CLIENT_DIGEST_RE.search(text):
        raise PagesAuditError("HTML_RUNTIME_VERIFICATION_CLAIM", public_path=public_path)
    for anchor in parser.external_anchors:
        if (
            anchor.href not in EXTERNAL_LINK_ALLOWLIST
            or anchor.target != "_blank"
            or anchor.rel != {"noopener", "noreferrer"}
        ):
            raise PagesAuditError("HTML_EXTERNAL_LINK", public_path=public_path)
    for tag, value in parser.internal_references:
        _validate_internal_reference(tag, value, public_path=public_path)
    if parser.url_records != _expected_url_records(
        public_path, css_relative=css_relative, svg_relative=svg_relative
    ):
        raise PagesAuditError("HTML_WIRING_MISMATCH", public_path=public_path)


def _normalize_css_for_scan(text: str) -> str:
    def replace_escape(match: re.Match[str]) -> str:
        hex_value, single = match.groups()
        if hex_value is not None:
            try:
                return chr(int(hex_value, 16))
            except ValueError:
                return ""
        return single or ""

    without_comments = _CSS_COMMENT_RE.sub("", text)
    decoded = _CSS_ESCAPE_RE.sub(replace_escape, without_comments)
    return decoded.casefold()


def _verify_css(path: Path, public_path: str) -> None:
    if path.stat().st_size > MAX_CSS_BYTES:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path=public_path)
    text = _decode_utf8(path, public_path)
    _assert_no_path_or_secret_leak(text, public_path)
    normalized = _normalize_css_for_scan(text)
    if (
        _CSS_URL_RE.search(normalized)
        or "@import" in normalized
        or "image-set(" in normalized
        or "@font-face" in normalized
        or "https://" in normalized
        or "http://" in normalized
        or "//" in normalized
        or "data:" in normalized
        or "javascript:" in normalized
    ):
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
    if _sha256_path(path) != EXPECTED_PUBLIC_SVG_SHA256:
        raise PagesAuditError("SVG_PUBLIC_FILENAME", public_path=path.as_posix())


def _is_reparse_point(path_stat: os.stat_result) -> bool:
    return bool(
        getattr(path_stat, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _extract_site_source_footer(index_path: Path) -> tuple[str, str, str]:
    text = _decode_utf8(index_path, "index.html")
    match = _SITE_SOURCE_FOOTER_RE.search(text)
    if match is None:
        raise PagesAuditError("HTML_SOURCE_FOOTER", public_path="index.html")
    return (
        match.group("site_source"),
        match.group("tag_object"),
        match.group("peeled_commit"),
    )


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
    manifest_payload = json.loads(
        _decode_utf8(publish / "pages-manifest.json", "pages-manifest.json")
    )
    source_date_epoch = manifest_payload.get("source_date_epoch")
    site_source_sha = manifest_payload.get("site_source_sha")
    if not isinstance(source_date_epoch, int) or not isinstance(site_source_sha, str):
        raise PagesAuditError("SBOM_STRUCTURE", public_path="sbom.spdx.json")
    expected_payload = _expected_spdx_payload(
        site_source_sha,
        source_date_epoch,
        tuple(actual_records[path] for path in _publish_paths(publish) if path in actual_records),
    )
    if payload != expected_payload:
        raise PagesAuditError("SBOM_STRUCTURE", public_path="sbom.spdx.json")
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
    source_date_epoch = payload.get("source_date_epoch")
    if not isinstance(site_source_sha, str) or not isinstance(source_date_epoch, int):
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
    footer_site_source, footer_tag_object, footer_peeled_commit = _extract_site_source_footer(
        publish / "index.html"
    )
    if (
        footer_site_source != site_source_sha
        or footer_tag_object != TAG_OBJECT
        or footer_peeled_commit != PEELED_COMMIT
    ):
        raise PagesAuditError("MANIFEST_STRUCTURE", public_path="pages-manifest.json")
    expected_payload = _expected_manifest_payload(
        site_source_sha,
        source_date_epoch,
        tuple(actual_records.values()),
        publish_tree_sha256,
        repository=None,
    )
    if payload != expected_payload:
        raise PagesAuditError("MANIFEST_STRUCTURE", public_path="pages-manifest.json")
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
    reports = _require_existing_directory(
        reports,
        missing_code="REPORT_MISSING",
        unsafe_code="REPORT_SYMLINK",
        special_code="REPORT_SPECIAL_FILE",
        public_path="reports",
    )
    for path in sorted(reports.rglob("*")):
        relative_path = path.relative_to(reports).as_posix()
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
            raise PagesAuditError("REPORT_SYMLINK", public_path=relative_path)
        if stat.S_ISDIR(path_stat.st_mode):
            if relative_path == REVIEW_SCREENSHOT_DIRECTORY:
                continue
            if relative_path.startswith(f"{REVIEW_SCREENSHOT_DIRECTORY}/"):
                continue
            raise PagesAuditError("REPORT_EXTRA_FILE", public_path=relative_path)
        if not stat.S_ISREG(path_stat.st_mode):
            raise PagesAuditError("REPORT_SPECIAL_FILE", public_path=relative_path)
        if relative_path in REVIEW_REPORT_FILES:
            continue
        if (
            relative_path.startswith(f"{REVIEW_SCREENSHOT_DIRECTORY}/")
            and path.suffix == REVIEW_SCREENSHOT_SUFFIX
        ):
            continue
        raise PagesAuditError("REPORT_EXTRA_FILE", public_path=relative_path)
    for filename in REVIEW_REPORT_FILES:
        if not (reports / filename).is_file():
            raise PagesAuditError("REPORT_MISSING", public_path=filename)
    zoom_payload = json.loads((reports / "zoom.json").read_text("utf-8"))
    manual_records = zoom_payload.get(MANUAL_BROWSER_ZOOM_FIELD)
    if not isinstance(manual_records, list):
        raise PagesAuditError("REPORT_MANUAL_ZOOM_REQUIRED", public_path="zoom.json")
    seen = {
        (item.get("browser"), str(item.get("revision")), item.get("status"))
        for item in manual_records
    }
    for browser, revision in EXPECTED_BROWSER_REVISIONS.items():
        if (browser, revision, "PASS") not in seen:
            raise PagesAuditError("REPORT_MANUAL_ZOOM_REQUIRED", public_path="zoom.json")
    return _report_records(reports)


def _copy_publish_individually(
    source_publish: Path, destination_publish: Path
) -> tuple[_FileRecord, ...]:
    source_records = _collect_records(source_publish, include_manifest=True, include_sbom=True)
    destination_publish.mkdir(parents=True, exist_ok=True)
    (destination_publish / "assets").mkdir(parents=True, exist_ok=True)
    for record in source_records:
        source = _require_existing_regular_file(
            source_publish / record.path,
            code="TREE_SYMLINK" if record.path == "." else "TREE_SPECIAL_FILE",
            public_path=record.path,
        )
        source_stat = source.lstat()
        if stat.S_ISLNK(source_stat.st_mode) or _is_reparse_point(source_stat):
            raise PagesAuditError("TREE_SYMLINK", public_path=record.path)
        if not stat.S_ISREG(source_stat.st_mode):
            raise PagesAuditError("TREE_SPECIAL_FILE", public_path=record.path)
        payload = source.read_bytes()
        if len(payload) != record.bytes_size or _sha256_bytes(payload) != record.sha256:
            raise PagesAuditError("TREE_COMPARE_MISMATCH")
        target = destination_publish / record.path
        _write_bytes_exclusive(target, payload)
        copied_record = _file_record(target, record.path)
        if copied_record != record:
            raise PagesAuditError("TREE_COMPARE_MISMATCH")
    return _collect_records(destination_publish, include_manifest=True, include_sbom=True)


def _copy_reports_individually(reports: Path, destination: Path) -> tuple[_FileRecord, ...]:
    copied_records: list[_FileRecord] = []
    for record in _verify_reports(reports):
        source = _require_existing_regular_file(
            reports / record.path,
            code="REPORT_SYMLINK" if record.path == "reports" else "REPORT_SPECIAL_FILE",
            public_path=record.path,
        )
        source_stat = source.lstat()
        if stat.S_ISLNK(source_stat.st_mode) or _is_reparse_point(source_stat):
            raise PagesAuditError("REPORT_SYMLINK", public_path=record.path)
        if not stat.S_ISREG(source_stat.st_mode):
            raise PagesAuditError("REPORT_SPECIAL_FILE", public_path=record.path)
        payload = source.read_bytes()
        if len(payload) != record.bytes_size or _sha256_bytes(payload) != record.sha256:
            raise PagesAuditError("REPORT_COPY_MISMATCH", public_path=record.path)
        target = destination / record.path
        _write_bytes_exclusive(target, payload)
        copied_record = _file_record(target, record.path)
        if copied_record != record:
            raise PagesAuditError("REPORT_COPY_MISMATCH", public_path=record.path)
        copied_records.append(copied_record)
    copied = tuple(copied_records)
    if _verify_reports(destination) != copied:
        raise PagesAuditError("REPORT_COPY_MISMATCH", public_path="reports")
    return copied


def _verify_review_export_layout(export_root: Path) -> None:
    export_stat = export_root.lstat()
    if (
        stat.S_ISLNK(export_stat.st_mode)
        or _is_reparse_point(export_stat)
        or not stat.S_ISDIR(export_stat.st_mode)
    ):
        raise PagesAuditError("CENTRAL_RECEIPT_PATH_INVALID")
    allowed_root_entries = {"publish", "reports", "review-receipt.json"}
    for path in export_root.iterdir():
        relative = path.relative_to(export_root).as_posix()
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
            raise PagesAuditError("CENTRAL_RECEIPT_PATH_INVALID")
        if relative not in allowed_root_entries:
            raise PagesAuditError("CENTRAL_RECEIPT_PATH_INVALID")


def build_site(
    repository: Path,
    output: Path,
    site_source_sha: str,
    source_date_epoch: int,
) -> BuildResult:
    repository = _require_existing_directory(
        repository,
        missing_code="REPOSITORY_PATH_UNSAFE",
        unsafe_code="REPOSITORY_PATH_UNSAFE",
        special_code="REPOSITORY_PATH_UNSAFE",
        public_path=repository.name or ".",
    )
    output, output_preexisting_empty = _prepare_output_directory(
        output,
        public_path=output.name or ".",
    )
    normalized_sha = normalize_site_source_sha(repository, site_source_sha)
    output_parent = _ensure_safe_directory(
        output.parent,
        code="OUTPUT_PATH_UNSAFE",
        public_path=output.parent.name or ".",
    )
    with tempfile.TemporaryDirectory(prefix="woundscope-pages-", dir=output.parent) as temp_dir:
        staging_root = Path(temp_dir)
        snapshot_root = staging_root / "snapshot"
        publish = staging_root / "publish"
        publish.mkdir()
        site_root, license_bytes = _build_site_snapshot(repository, normalized_sha, snapshot_root)
        evidence = load_public_evidence(repository)
        verified_svg = load_verified_svg(repository, evidence)
        rendered = render_site(evidence, verified_svg, normalized_sha, site_root)
        authored_css = _read_commit_blob(repository, normalized_sha, "site/site.css")
        if rendered.css != authored_css:
            raise PagesAuditError("CSS_SOURCE_MISMATCH", public_path="site.css")
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
            _manifest_payload(
                normalized_sha,
                evidence,
                source_date_epoch,
                manifest_records,
                publish_tree_sha256,
                repository=repository,
            ),
        )
        verified = verify_publish_tree(publish)
        if output_preexisting_empty:
            output = _require_existing_directory(
                output,
                missing_code="OUTPUT_EXISTS",
                unsafe_code="OUTPUT_PATH_UNSAFE",
                special_code="OUTPUT_PATH_UNSAFE",
                public_path=output.name or ".",
            )
            if any(output.iterdir()):
                raise PagesAuditError("OUTPUT_EXISTS", public_path=output.name or ".")
            output.rmdir()
        _ensure_safe_directory(
            output_parent, code="OUTPUT_PATH_UNSAFE", public_path=output_parent.name or "."
        )
        if _existing_lstat(output) is not None:
            raise PagesAuditError("OUTPUT_EXISTS", public_path=output.name or ".")
        publish.rename(output)
        return BuildResult(
            publish=output,
            site_source_sha=verified.site_source_sha,
            manifest_sha256=verified.manifest_sha256,
            sbom_sha256=verified.sbom_sha256,
            publish_tree_sha256=verified.publish_tree_sha256,
        )


def verify_publish_tree(publish: Path) -> VerifiedPublish:
    publish = _require_existing_directory(
        publish,
        missing_code="TREE_MISSING_FILE",
        unsafe_code="TREE_SYMLINK",
        special_code="TREE_SPECIAL_FILE",
        public_path=".",
    )
    css_relative, svg_relative = _verify_inventory(publish)
    total_bytes = 0
    for relative_path in _publish_paths(publish):
        path = publish / relative_path
        path_stat = _existing_lstat(path)
        if path_stat is None:
            raise PagesAuditError("TREE_MISSING_FILE", public_path=relative_path)
        if stat.S_ISLNK(path_stat.st_mode) or _is_reparse_point(path_stat):
            raise PagesAuditError("TREE_SYMLINK", public_path=relative_path)
        if not stat.S_ISREG(path_stat.st_mode):
            raise PagesAuditError("TREE_SPECIAL_FILE", public_path=relative_path)
        total_bytes += path.stat().st_size
    if total_bytes > MAX_TOTAL_PUBLISH_BYTES:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path="publish")
    if (publish / ".nojekyll").stat().st_size != PUBLISH_FILE_BUDGETS[".nojekyll"]:
        raise PagesAuditError("TREE_BUDGET_EXCEEDED", public_path=".nojekyll")
    _verify_html(
        publish / "index.html",
        "index.html",
        css_relative=css_relative,
        svg_relative=svg_relative,
    )
    _verify_html(
        publish / "404.html",
        "404.html",
        css_relative=css_relative,
        svg_relative=svg_relative,
    )
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
    export_root = _validate_path_components(
        export_root,
        code="OUTPUT_PATH_UNSAFE",
        public_path=export_root.name or ".",
    )
    if _existing_lstat(export_root) is not None:
        raise PagesAuditError("OUTPUT_EXISTS", public_path=export_root.name or ".")
    export_parent = _ensure_safe_directory(
        export_root.parent,
        code="OUTPUT_PATH_UNSAFE",
        public_path=export_root.parent.name or ".",
    )
    with tempfile.TemporaryDirectory(
        prefix="woundscope-review-", dir=export_root.parent
    ) as temp_dir:
        staging_root = Path(temp_dir) / export_root.name
        staging_root.mkdir(parents=True, exist_ok=True)
        publish_records = _copy_publish_individually(verified.publish, staging_root / "publish")
        if (
            verify_publish_tree(verified.publish).publish_tree_sha256
            != verified.publish_tree_sha256
        ):
            raise PagesAuditError("TREE_COMPARE_MISMATCH")
        destination_verified = verify_publish_tree(staging_root / "publish")
        copied_report_records = _copy_reports_individually(reports, staging_root / "reports")
        if _verify_reports(reports) != report_records:
            raise PagesAuditError("REPORT_COPY_MISMATCH", public_path="reports")
        receipt = {
            "evidence_peeled_commit": PEELED_COMMIT,
            "evidence_tag_object": TAG_OBJECT,
            "manifest_sha256": destination_verified.manifest_sha256,
            "publish_tree_sha256": destination_verified.publish_tree_sha256,
            "report_hashes": [
                {"bytes": record.bytes_size, "path": record.path, "sha256": record.sha256}
                for record in sorted(
                    copied_report_records, key=lambda item: item.path.encode("utf-8")
                )
            ],
            "review_payload_sha256": _review_payload_sha256(publish_records, copied_report_records),
            "sbom_sha256": destination_verified.sbom_sha256,
            "site_source_sha": destination_verified.site_source_sha,
        }
        receipt_path = staging_root / "review-receipt.json"
        _write_bytes(receipt_path, _json_bytes(receipt))
        verify_publish_tree(staging_root / "publish")
        if _verify_reports(staging_root / "reports") != copied_report_records:
            raise PagesAuditError("REPORT_COPY_MISMATCH", public_path="reports")
        _verify_review_export_layout(staging_root)
        if report_records != copied_report_records:
            raise PagesAuditError("REPORT_COPY_MISMATCH", public_path="reports")
        _ensure_safe_directory(
            export_parent, code="OUTPUT_PATH_UNSAFE", public_path=export_parent.name or "."
        )
        if _existing_lstat(export_root) is not None:
            raise PagesAuditError("OUTPUT_EXISTS", public_path=export_root.name or ".")
        staging_root.rename(export_root)
    return export_root / "review-receipt.json"


def _git_is_dirty(repository: Path) -> bool:
    return bool(_run_git_text(repository, ["status", "--porcelain=v1", "-uno"], code="GIT_DIRTY"))


def record_central_seal(
    repository: Path,
    receipt: Path,
    output: Path,
    approved_site_source: str,
    reviewer: str,
    approval_id: str,
) -> Path:
    repository = _require_existing_directory(
        repository,
        missing_code="REPOSITORY_PATH_UNSAFE",
        unsafe_code="REPOSITORY_PATH_UNSAFE",
        special_code="REPOSITORY_PATH_UNSAFE",
        public_path=repository.name or ".",
    )
    approved_site_source = _require_hex40(approved_site_source, code="SITE_SOURCE_SHA_INVALID")
    if reviewer != _REPORTED_OWNER:
        raise PagesAuditError("CENTRAL_REVIEWER_INVALID")
    if not _APPROVAL_ID_RE.fullmatch(approval_id):
        raise PagesAuditError("CENTRAL_APPROVAL_ID_INVALID")
    output = _validate_path_components(
        output,
        code="CENTRAL_SEAL_PATH_INVALID",
        public_path="CENTRAL_SEAL.json",
    )
    receipt = _validate_path_components(
        receipt,
        code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="review-receipt.json",
    )
    if receipt.name != "review-receipt.json":
        raise PagesAuditError("CENTRAL_RECEIPT_PATH_INVALID")
    receipt = _require_existing_regular_file(
        receipt,
        code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="review-receipt.json",
    )
    export_root = receipt.parent
    _require_existing_directory(
        export_root,
        missing_code="CENTRAL_RECEIPT_PATH_INVALID",
        unsafe_code="CENTRAL_RECEIPT_PATH_INVALID",
        special_code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="review-export",
    )
    _require_existing_directory(
        export_root / "publish",
        missing_code="CENTRAL_RECEIPT_PATH_INVALID",
        unsafe_code="CENTRAL_RECEIPT_PATH_INVALID",
        special_code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="publish",
    )
    _require_existing_directory(
        export_root / "reports",
        missing_code="CENTRAL_RECEIPT_PATH_INVALID",
        unsafe_code="CENTRAL_RECEIPT_PATH_INVALID",
        special_code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="reports",
    )
    if output != export_root.parent / "CENTRAL_SEAL.json":
        raise PagesAuditError("CENTRAL_SEAL_PATH_INVALID")
    if _git_is_dirty(repository):
        raise PagesAuditError("GIT_DIRTY")
    if normalize_site_source_sha(repository, "HEAD") != approved_site_source:
        raise PagesAuditError("SITE_SOURCE_SHA_MISMATCH")
    receipt_payload = json.loads(receipt.read_text("utf-8"))
    if receipt_payload.get("site_source_sha") != approved_site_source:
        raise PagesAuditError("SITE_SOURCE_SHA_MISMATCH")
    output = _validate_path_components(
        output,
        code="CENTRAL_SEAL_PATH_INVALID",
        public_path="CENTRAL_SEAL.json",
    )
    _require_existing_regular_file(
        receipt,
        code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="review-receipt.json",
    )
    _require_existing_directory(
        export_root,
        missing_code="CENTRAL_RECEIPT_PATH_INVALID",
        unsafe_code="CENTRAL_RECEIPT_PATH_INVALID",
        special_code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="review-export",
    )
    _require_existing_directory(
        export_root / "publish",
        missing_code="CENTRAL_RECEIPT_PATH_INVALID",
        unsafe_code="CENTRAL_RECEIPT_PATH_INVALID",
        special_code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="publish",
    )
    _require_existing_directory(
        export_root / "reports",
        missing_code="CENTRAL_RECEIPT_PATH_INVALID",
        unsafe_code="CENTRAL_RECEIPT_PATH_INVALID",
        special_code="CENTRAL_RECEIPT_PATH_INVALID",
        public_path="reports",
    )
    _require_existing_directory(
        output.parent,
        missing_code="CENTRAL_SEAL_PATH_INVALID",
        unsafe_code="CENTRAL_SEAL_PATH_INVALID",
        special_code="CENTRAL_SEAL_PATH_INVALID",
        public_path=output.parent.name or ".",
    )
    if _existing_lstat(output) is not None:
        raise PagesAuditError("OUTPUT_EXISTS", public_path=output.name)
    _verify_review_export_layout(export_root)
    payload = {
        "approval_id": approval_id,
        "decision": "approved",
        "evidence_peeled_commit": receipt_payload.get("evidence_peeled_commit"),
        "evidence_tag_object": receipt_payload.get("evidence_tag_object"),
        "receipt_sha256": _sha256_bytes(receipt.read_bytes()),
        "reviewer": reviewer,
        "site_source_sha": approved_site_source,
    }
    _write_bytes_exclusive(output, _json_bytes(payload))
    return output
