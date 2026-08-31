"""Render the zero-JavaScript Pages source from pinned public evidence."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from json import JSONDecodeError
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .constants import EXPECTED_MODEL_DISPLAY_NAMES
from .evidence import PublicEvidence
from .svg_contract import VerifiedSvg

_INDEX_TEMPLATE = "index.template.html"
_NOT_FOUND_TEMPLATE = "404.template.html"
_SITE_CSS = "site.css"
_ALLOWLIST = "links.allowlist.json"
_NOTICES = "THIRD_PARTY_NOTICES.txt"
_EXPECTED_ALLOWLIST = (
    "https://doi.org/10.1038/s41598-020-78799-w",
    "https://github.com/kuotunyu/WoundScope",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/CITATION.cff",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/DATA_CARD.md",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/LICENSE",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/MODEL_CARD.md",
    "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/README.md",
    "https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.2",
    "https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge",
)
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_SLOT_RE = re.compile(r"{{([A-Z0-9_]+)}}")
_FORBIDDEN_URI_SCHEMES = ("data:", "javascript:", "mailto:")
_SHORTENER_HOSTS = frozenset(
    {
        "bit.ly",
        "buff.ly",
        "goo.gl",
        "is.gd",
        "ow.ly",
        "t.co",
        "tinyurl.com",
    }
)
_SITE_SOURCE_PATH = "/WoundScope/"
_EXPECTED_NOTICES_TEXT = """WoundScope Static Research Showcase — Third-Party Notices

Bundled third-party runtime packages: none.
The production site contains authored HTML/CSS, WoundScope project material under Apache-2.0, and a WoundScope-authored aggregate SVG projected from the pinned v0.2.2 Git evidence object.

Aggregate research-fact attribution (not bundled software or redistributed data):
FUSeg / Foot Ulcer Segmentation Challenge, pinned public source revision 42a272dfe0679f20675e826385925cb7562934b6.
Publication: https://doi.org/10.1038/s41598-020-78799-w
Source: https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge

No FUSeg image, mask, patient/sample identifier, model weight, ONNX artifact, or image-level result is redistributed by this site. Apache-2.0 does not assert ownership of FUSeg or model artifacts.

Build/review-only tools are reported separately in the review artifact and are not production runtime components.
"""


class RenderContractError(RuntimeError):
    """Stable, public-safe render contract failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RenderedSite:
    index_html: bytes
    not_found_html: bytes
    css: bytes
    notices: bytes


def escape_text(value: str) -> str:
    return html.escape(value, quote=True)


def _read_site_file_bytes(site_root: Path, filename: str) -> bytes:
    try:
        payload = (site_root / filename).read_bytes()
    except OSError:
        raise RenderContractError("SITE_FILE_READ") from None
    if payload.startswith(b"\xef\xbb\xbf"):
        raise RenderContractError("SITE_FILE_BOM")
    return payload


def _normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _read_site_text(site_root: Path, filename: str) -> str:
    payload = _read_site_file_bytes(site_root, filename)
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise RenderContractError("SITE_FILE_UTF8") from None
    return _normalize_lf(decoded)


def _read_normalized_site_bytes(site_root: Path, filename: str) -> bytes:
    return _read_site_text(site_root, filename).encode("utf-8")


def _require_hex40(value: str, *, code: str) -> str:
    if _HEX40_RE.fullmatch(value) is None:
        raise RenderContractError(code)
    return value


def _normalize_allowlist_url(url: str) -> str:
    if not url or url.casefold().startswith(_FORBIDDEN_URI_SCHEMES):
        raise RenderContractError("ALLOWLIST_SCHEME")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise RenderContractError("ALLOWLIST_SCHEME")
    if parts.query or parts.fragment:
        raise RenderContractError("ALLOWLIST_QUERY_OR_FRAGMENT")
    if parts.netloc.casefold() in _SHORTENER_HOSTS:
        raise RenderContractError("ALLOWLIST_SHORTENER")
    normalized_parts = SplitResult(
        scheme="https",
        netloc=parts.netloc,
        path=parts.path,
        query="",
        fragment="",
    )
    normalized = urlunsplit(normalized_parts)
    if normalized != url:
        raise RenderContractError("ALLOWLIST_NORMALIZATION")
    return normalized


def _load_allowlist(site_root: Path) -> tuple[str, ...]:
    raw = _read_site_text(site_root, _ALLOWLIST)
    try:
        data = json.loads(raw)
    except JSONDecodeError:
        raise RenderContractError("ALLOWLIST_JSON") from None
    if not isinstance(data, list):
        raise RenderContractError("ALLOWLIST_FORMAT")
    normalized = tuple(_normalize_allowlist_url(str(item)) for item in data)
    if len(normalized) != len(set(normalized)):
        raise RenderContractError("ALLOWLIST_DUPLICATE")
    if normalized != _EXPECTED_ALLOWLIST:
        raise RenderContractError("ALLOWLIST_MISMATCH")
    return normalized


def _format_decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001')):f}"


def _format_metric_pair(mean: Decimal, sd: Decimal) -> str:
    return f"{_format_decimal(mean)}±{_format_decimal(sd)}"


def _format_dice_cell(row) -> str:
    return (
        f"{_format_decimal(row.dice_mean)}±{_format_decimal(row.dice_sd)} "
        f"({_format_decimal(row.dice_ci_low)}–{_format_decimal(row.dice_ci_high)})"
    )


def _format_count(value: int) -> str:
    return f"{value:,}"


def _model_display_name(index: int) -> str:
    return EXPECTED_MODEL_DISPLAY_NAMES[index]


def _build_results_rows(evidence: PublicEvidence) -> str:
    rows: list[str] = []
    for index, row in enumerate(evidence.rows):
        cells = (
            f'                <th scope="row">{escape_text(_model_display_name(index))}</th>',
            f"                <td>{escape_text(row.loss)}</td>",
            f"                <td>{escape_text('/'.join(str(seed) for seed in row.seeds))}</td>",
            f"                <td>{escape_text(_format_dice_cell(row))}</td>",
            f"                <td>{escape_text(_format_metric_pair(row.iou_mean, row.iou_sd))}</td>",
            f"                <td>{escape_text(_format_metric_pair(row.precision_mean, row.precision_sd))}</td>",
            f"                <td>{escape_text(_format_metric_pair(row.recall_mean, row.recall_sd))}</td>",
            f"                <td>{escape_text(_format_metric_pair(row.specificity_mean, row.specificity_sd))}</td>",
        )
        rows.append("              <tr>\n" + "\n".join(cells) + "\n              </tr>")
    return "\n".join(rows)


def _render_template(template: str, replacements: dict[str, str]) -> str:
    slots = _SLOT_RE.findall(template)
    if len(slots) != len(set(slots)):
        raise RenderContractError("TEMPLATE_SLOT_DUPLICATE")
    slot_names = set(slots)
    replacement_names = set(replacements)
    if slot_names - replacement_names:
        raise RenderContractError("TEMPLATE_SLOT_MISSING")
    if replacement_names - slot_names:
        raise RenderContractError("TEMPLATE_SLOT_UNKNOWN")
    rendered = _SLOT_RE.sub(lambda match: replacements[match.group(1)], template)
    if "{{" in rendered or "}}" in rendered:
        raise RenderContractError("TEMPLATE_SLOT_UNPARSED")
    return rendered


def _load_notices_bytes(site_root: Path) -> bytes:
    notices_text = _read_site_text(site_root, _NOTICES)
    if notices_text != _EXPECTED_NOTICES_TEXT:
        raise RenderContractError("NOTICE_CONTENT")
    return notices_text.encode("utf-8")


def render_site(
    evidence: PublicEvidence,
    verified_svg: VerifiedSvg,
    site_source_sha: str,
    site_root: Path,
) -> RenderedSite:
    _require_hex40(site_source_sha, code="SITE_SOURCE_SHA")
    index_template = _read_site_text(site_root, _INDEX_TEMPLATE)
    not_found_template = _read_site_text(site_root, _NOT_FOUND_TEMPLATE)
    css_bytes = _read_normalized_site_bytes(site_root, _SITE_CSS)
    notices_bytes = _load_notices_bytes(site_root)
    allowlist = _load_allowlist(site_root)

    replacements = {
        "VALIDATION_IMAGES": escape_text(str(evidence.validation_images)),
        "BOOTSTRAP_ITERATIONS": escape_text(_format_count(evidence.bootstrap_iterations)),
        "RESULTS_ROWS": _build_results_rows(evidence),
        "VERIFIED_SVG_PATH": escape_text(
            f"{_SITE_SOURCE_PATH}assets/{verified_svg.public_filename}"
        ),
        "SVG_BLOB": escape_text(evidence.provenance.svg_blob),
        "SITE_REPOSITORY_URL": escape_text(allowlist[1]),
        "SITE_RELEASE_URL": escape_text(allowlist[7]),
        "README_URL": escape_text(allowlist[6]),
        "CITATION_URL": escape_text(allowlist[2]),
        "DATA_CARD_URL": escape_text(allowlist[3]),
        "MODEL_CARD_URL": escape_text(allowlist[5]),
        "LICENSE_URL": escape_text(allowlist[4]),
        "TAG_NAME": escape_text(evidence.provenance.tag_name),
        "SITE_SOURCE_SHA": escape_text(site_source_sha),
        "TAG_OBJECT": escape_text(evidence.provenance.tag_object),
        "PEELED_COMMIT": escape_text(evidence.provenance.peeled_commit),
        "README_BLOB": escape_text(evidence.provenance.readme_blob),
        "DOI_URL": escape_text(allowlist[0]),
        "DATASET_URL": escape_text(allowlist[8]),
        "MODEL_CARD_BLOB": escape_text(evidence.provenance.model_card_blob),
        "DATA_CARD_BLOB": escape_text(evidence.provenance.data_card_blob),
    }
    index_html = _render_template(index_template, replacements).encode("utf-8")
    not_found_html = _render_template(not_found_template, {}).encode("utf-8")
    return RenderedSite(
        index_html=index_html,
        not_found_html=not_found_html,
        css=css_bytes,
        notices=notices_bytes,
    )
