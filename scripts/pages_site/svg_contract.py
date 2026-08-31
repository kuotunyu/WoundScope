"""Verify the pinned public Pages SVG without reading worktree files."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .constants import (
    EXPECTED_MODEL_DISPLAY_NAMES,
    EXPECTED_PUBLIC_SVG_DESC,
    EXPECTED_PUBLIC_SVG_FILENAME,
    EXPECTED_PUBLIC_SVG_FOOTNOTE,
    EXPECTED_PUBLIC_SVG_HEADLINE,
    EXPECTED_PUBLIC_SVG_LENGTH,
    EXPECTED_PUBLIC_SVG_SHA256,
    EXPECTED_PUBLIC_SVG_SUBHEAD,
    EXPECTED_PUBLIC_SVG_TITLE,
)
from .evidence import PublicEvidence, read_git_object

_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
_SVG_PREFIX = f"{{{_SVG_NAMESPACE}}}"
_FORBIDDEN_XML_RE = re.compile(rb"<!DOCTYPE|<!ENTITY", re.IGNORECASE)
_FORBIDDEN_VALUE_RE = re.compile(rb"url\(|data:|http:|https:", re.IGNORECASE)
_FORBIDDEN_TEXT_TOKENS = (
    "patient",
    "sample_id",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    "prediction",
    "inference",
    "deploy",
    "deployment",
    "about",
    "network",
    "huggingface",
    "hugging face",
)
_ALLOWED_ATTRIBUTES = {
    "svg": frozenset({"width", "height", "viewBox", "role", "aria-labelledby"}),
    "title": frozenset({"id"}),
    "desc": frozenset({"id"}),
    "rect": frozenset({"x", "y", "width", "height", "rx", "fill"}),
    "text": frozenset({"x", "y", "fill", "font-family", "font-size", "font-weight", "text-anchor"}),
    "g": frozenset({"fill", "stroke", "stroke-width", "font-family", "font-size", "text-anchor"}),
    "line": frozenset({"x1", "y1", "x2", "y2"}),
}


class SvgContractError(RuntimeError):
    """Stable, public-safe SVG contract failure."""


@dataclass(frozen=True, slots=True)
class VerifiedSvg:
    bytes_value: bytes
    sha256: str
    git_blob: str
    public_filename: str


def _git_blob_id(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()


def _decimal_token(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001')):f}"


def _iter_text_nodes(root: ET.Element) -> list[str]:
    text_values: list[str] = []
    for element in root.iter():
        if element.text is not None:
            value = element.text.strip()
            if value:
                text_values.append(value)
    return text_values


def _text_content(element: ET.Element, *, code: str) -> str:
    text_value = (element.text or "").strip()
    if not text_value:
        raise SvgContractError(code)
    return text_value


def _validate_element_tree(root: ET.Element) -> None:
    if root.tag != f"{_SVG_PREFIX}svg":
        raise SvgContractError("SVG_ROOT")
    if root.attrib.get("role") != "img":
        raise SvgContractError("SVG_ROLE")
    if root.attrib.get("aria-labelledby") != "title desc":
        raise SvgContractError("SVG_ARIA_LABELLED_BY")

    for element in root.iter():
        if not element.tag.startswith(_SVG_PREFIX):
            raise SvgContractError("SVG_ELEMENT")
        local_name = element.tag.removeprefix(_SVG_PREFIX)
        allowed_attributes = _ALLOWED_ATTRIBUTES.get(local_name)
        if allowed_attributes is None:
            raise SvgContractError("SVG_ELEMENT")
        for attribute_name, attribute_value in element.attrib.items():
            local_attribute = attribute_name.rsplit("}", maxsplit=1)[-1]
            if local_attribute.startswith("on"):
                raise SvgContractError("SVG_ATTR")
            if local_attribute not in allowed_attributes:
                raise SvgContractError("SVG_ATTR")
            if _FORBIDDEN_VALUE_RE.search(attribute_value.encode("utf-8")) is not None:
                raise SvgContractError("SVG_VALUE")


def _require_singleton(
    root: ET.Element,
    tag_name: str,
    expected_id: str,
    expected_text: str,
    *,
    count_code: str,
    id_code: str,
    text_code: str,
) -> None:
    elements = root.findall(f"{_SVG_PREFIX}{tag_name}")
    if len(elements) != 1:
        raise SvgContractError(count_code)
    if elements[0].attrib.get("id") != expected_id:
        raise SvgContractError(id_code)
    text_value = _text_content(elements[0], code=text_code)
    if text_value != expected_text:
        raise SvgContractError(text_code)


def _require_chart_group(root: ET.Element) -> ET.Element:
    groups = [
        element
        for element in root.findall(f"{_SVG_PREFIX}g")
        if element.attrib == {"font-family": "Arial, sans-serif"}
    ]
    if len(groups) != 1:
        raise SvgContractError("SVG_ROW_STRUCTURE")
    return groups[0]


def _validate_row_metrics(chart_group: ET.Element, evidence: PublicEvidence) -> None:
    children = list(chart_group)
    expected_children_per_row = 7
    if len(children) != len(evidence.rows) * expected_children_per_row:
        raise SvgContractError("SVG_ROW_STRUCTURE")

    for row_index, (display_name, evidence_row) in enumerate(
        zip(EXPECTED_MODEL_DISPLAY_NAMES, evidence.rows, strict=True)
    ):
        offset = row_index * expected_children_per_row
        model_title, dice_label, dice_bar, dice_value, iou_label, iou_bar, iou_value = children[
            offset : offset + expected_children_per_row
        ]
        expected_tags = (
            f"{_SVG_PREFIX}text",
            f"{_SVG_PREFIX}text",
            f"{_SVG_PREFIX}rect",
            f"{_SVG_PREFIX}text",
            f"{_SVG_PREFIX}text",
            f"{_SVG_PREFIX}rect",
            f"{_SVG_PREFIX}text",
        )
        actual_tags = tuple(
            child.tag
            for child in (
                model_title,
                dice_label,
                dice_bar,
                dice_value,
                iou_label,
                iou_bar,
                iou_value,
            )
        )
        if actual_tags != expected_tags:
            raise SvgContractError("SVG_ROW_STRUCTURE")
        if _text_content(model_title, code="SVG_ROW_MODEL") != display_name:
            raise SvgContractError("SVG_ROW_MODEL")
        if _text_content(dice_label, code="SVG_ROW_LABEL") != "Dice":
            raise SvgContractError("SVG_ROW_LABEL")
        if _text_content(iou_label, code="SVG_ROW_LABEL") != "IoU":
            raise SvgContractError("SVG_ROW_LABEL")
        if _text_content(dice_value, code="SVG_ROW_VALUE") != _decimal_token(
            evidence_row.dice_mean
        ):
            raise SvgContractError("SVG_ROW_VALUE")
        if _text_content(iou_value, code="SVG_ROW_VALUE") != _decimal_token(evidence_row.iou_mean):
            raise SvgContractError("SVG_ROW_VALUE")


def _validate_text_contract(root: ET.Element, evidence: PublicEvidence) -> None:
    _require_singleton(
        root,
        "title",
        "title",
        EXPECTED_PUBLIC_SVG_TITLE,
        count_code="SVG_TITLE_COUNT",
        id_code="SVG_TITLE_ID",
        text_code="SVG_TITLE_TEXT",
    )
    _require_singleton(
        root,
        "desc",
        "desc",
        EXPECTED_PUBLIC_SVG_DESC,
        count_code="SVG_DESC_COUNT",
        id_code="SVG_DESC_ID",
        text_code="SVG_DESC_TEXT",
    )

    text_values = _iter_text_nodes(root)
    required_values = [
        EXPECTED_PUBLIC_SVG_TITLE,
        EXPECTED_PUBLIC_SVG_DESC,
        EXPECTED_PUBLIC_SVG_HEADLINE,
        EXPECTED_PUBLIC_SVG_SUBHEAD,
        *EXPECTED_MODEL_DISPLAY_NAMES,
        EXPECTED_PUBLIC_SVG_FOOTNOTE,
    ]
    for required_value in required_values:
        if text_values.count(required_value) != 1:
            raise SvgContractError("SVG_TEXT")

    chart_group = _require_chart_group(root)
    _validate_row_metrics(chart_group, evidence)

    lowered_text = "\n".join(text_values).casefold()
    for forbidden_token in _FORBIDDEN_TEXT_TOKENS:
        if forbidden_token in lowered_text:
            raise SvgContractError("SVG_TEXT")


def verify_svg_bytes(
    svg_bytes: bytes,
    evidence: PublicEvidence,
    enforce_exact_bytes: bool = True,
) -> VerifiedSvg:
    if _FORBIDDEN_XML_RE.search(svg_bytes) is not None:
        raise SvgContractError("SVG_XML_PROLOG")
    try:
        root = ET.fromstring(svg_bytes)
    except ET.ParseError as error:
        raise SvgContractError("SVG_XML_PARSE") from error

    _validate_element_tree(root)
    _validate_text_contract(root, evidence)

    sha256 = hashlib.sha256(svg_bytes).hexdigest()
    git_blob = _git_blob_id(svg_bytes)
    public_filename = f"model-comparison-{sha256[:16]}.svg"
    verified = VerifiedSvg(
        bytes_value=svg_bytes,
        sha256=sha256,
        git_blob=git_blob,
        public_filename=public_filename,
    )
    if enforce_exact_bytes:
        if git_blob != evidence.provenance.svg_blob:
            raise SvgContractError("SVG_GIT_BLOB")
        if len(svg_bytes) != EXPECTED_PUBLIC_SVG_LENGTH:
            raise SvgContractError("SVG_LENGTH")
        if sha256 != EXPECTED_PUBLIC_SVG_SHA256:
            raise SvgContractError("SVG_SHA256")
        if public_filename != EXPECTED_PUBLIC_SVG_FILENAME:
            raise SvgContractError("SVG_PUBLIC_FILENAME")
    return verified


def load_verified_svg(repository: Path, evidence: PublicEvidence) -> VerifiedSvg:
    svg_bytes = read_git_object(repository, evidence.provenance.svg_blob, "blob")
    return verify_svg_bytes(svg_bytes, evidence, enforce_exact_bytes=True)
