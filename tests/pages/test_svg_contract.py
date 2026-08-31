from __future__ import annotations

import importlib
import sys
from decimal import Decimal
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
EXPECTED_SVG_LENGTH = 3009
EXPECTED_SVG_SHA256 = "1eafa7c35b06928b6cfc2910326f9c0adaf88098ab3a734ba43e16914fd7814d"
EXPECTED_PUBLIC_FILENAME = "model-comparison-1eafa7c35b06928b.svg"


def _import_module(name: str):
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(REPOSITORY))
        return importlib.import_module(name)
    finally:
        sys.path[:] = original_path


def _evidence_exports() -> tuple[object, object]:
    module = _import_module("scripts.pages_site.evidence")
    return module.load_public_evidence, module.read_git_object


def _svg_exports() -> tuple[type[Exception], object, object, object]:
    module = _import_module("scripts.pages_site.svg_contract")
    return module.SvgContractError, module.load_verified_svg, module.verify_svg_bytes, module


def _approved_svg_bytes() -> tuple[bytes, object]:
    load_public_evidence, read_git_object = _evidence_exports()
    evidence = load_public_evidence(REPOSITORY)
    return read_git_object(REPOSITORY, evidence.provenance.svg_blob, "blob"), evidence


def _mutate_metric_token(value: Decimal) -> str:
    return f"{(value + Decimal('0.0001')).quantize(Decimal('0.0001')):f}"


def _decimal_token(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.0001')):f}"


def _swap_tokens(payload: bytes, first: str, second: str) -> bytes:
    sentinel = "__swap__sentinel__"
    mutated = payload.replace(first.encode("utf-8"), sentinel.encode("utf-8"), 1)
    mutated = mutated.replace(second.encode("utf-8"), first.encode("utf-8"), 1)
    return mutated.replace(sentinel.encode("utf-8"), second.encode("utf-8"), 1)


def test_exact_svg_matches_evidence_without_worktree_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_public_evidence, _read_git_object = _evidence_exports()
    _svg_contract_error, load_verified_svg, _verify_svg_bytes, module = _svg_exports()
    evidence = load_public_evidence(REPOSITORY)

    def forbid_worktree_read(*args, **kwargs):
        raise AssertionError("WORKTREE_READ_FORBIDDEN")

    monkeypatch.setattr(module.Path, "read_bytes", forbid_worktree_read)
    monkeypatch.setattr(module.Path, "read_text", forbid_worktree_read)
    monkeypatch.setattr(module.Path, "open", forbid_worktree_read)

    verified = load_verified_svg(REPOSITORY, evidence)

    assert len(verified.bytes_value) == EXPECTED_SVG_LENGTH
    assert verified.sha256 == EXPECTED_SVG_SHA256
    assert verified.git_blob == evidence.provenance.svg_blob
    assert verified.public_filename == EXPECTED_PUBLIC_FILENAME


def test_rejects_semantically_equivalent_byte_drift_when_exact_lock_enabled() -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()
    mutated = source.replace(b"\n  <desc", b"\n <desc", 1)

    assert mutated != source
    with pytest.raises(svg_contract_error, match="SVG_GIT_BLOB"):
        verify_svg_bytes(mutated, evidence, enforce_exact_bytes=True)


@pytest.mark.parametrize(
    ("needle", "replacement", "code"),
    [
        (b'<title id="title">', b'<title id="title-alt">', "SVG_TITLE_ID"),
        (b'<desc id="desc">', b'<desc id="desc-alt">', "SVG_DESC_ID"),
    ],
)
def test_rejects_accessibility_label_id_drift(needle: bytes, replacement: bytes, code: str) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()

    with pytest.raises(svg_contract_error, match=code):
        verify_svg_bytes(
            source.replace(needle, replacement, 1), evidence, enforce_exact_bytes=False
        )


@pytest.mark.parametrize(
    ("needle", "replacement", "code"),
    [
        (b'role="img"', b'role="presentation"', "SVG_ROLE"),
        (b'aria-labelledby="title desc"', b'aria-labelledby="title"', "SVG_ARIA_LABELLED_BY"),
        (b"</svg>", b"<script>0</script></svg>", "SVG_ELEMENT"),
        (b"</svg>", b'<image href="https://example.invalid/x"/></svg>', "SVG_ELEMENT"),
    ],
)
def test_rejects_mutated_svg(needle: bytes, replacement: bytes, code: str) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()

    with pytest.raises(svg_contract_error, match=code):
        verify_svg_bytes(source.replace(needle, replacement), evidence, enforce_exact_bytes=False)


@pytest.mark.parametrize(
    ("replacement_pairs", "code"),
    [
        (
            (
                (
                    (
                        b'  <title id="title">WoundScope locked official-validation aggregate '
                        b"comparison</title>\n"
                    ),
                    b"",
                ),
            ),
            "SVG_TITLE_COUNT",
        ),
        (
            (
                (
                    b'  <desc id="desc">',
                    (
                        b'  <title id="title">WoundScope locked official-validation aggregate '
                        b'comparison</title>\n  <desc id="desc">'
                    ),
                ),
            ),
            "SVG_TITLE_COUNT",
        ),
        (
            (
                (
                    (
                        b'  <desc id="desc">EfficientNet-B0 U-Net and SegFormer-B0 aggregate '
                        b"Dice and IoU across three training seeds on locked official "
                        b"validation.</desc>\n"
                    ),
                    b"",
                ),
            ),
            "SVG_DESC_COUNT",
        ),
        (
            (
                (
                    b'  <rect width="1200" height="520" fill="#f8fafc"/>',
                    (
                        b'  <desc id="desc">EfficientNet-B0 U-Net and SegFormer-B0 aggregate '
                        b"Dice and IoU across three training seeds on locked official "
                        b'validation.</desc>\n  <desc id="desc">duplicate</desc>\n'
                        b'  <rect width="1200" height="520" fill="#f8fafc"/>'
                    ),
                ),
            ),
            "SVG_DESC_COUNT",
        ),
        (
            (
                (
                    b"WoundScope locked official-validation aggregate comparison",
                    b"",
                ),
            ),
            "SVG_TITLE_TEXT",
        ),
        (
            (
                (
                    b"EfficientNet-B0 U-Net and SegFormer-B0 aggregate Dice and IoU across three "
                    b"training seeds on locked official validation.",
                    b"",
                ),
            ),
            "SVG_DESC_TEXT",
        ),
    ],
)
def test_rejects_accessibility_contract_drift(
    replacement_pairs: tuple[tuple[bytes, bytes], ...],
    code: str,
) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    mutated, evidence = _approved_svg_bytes()
    for needle, replacement in replacement_pairs:
        mutated = mutated.replace(needle, replacement, 1)

    with pytest.raises(svg_contract_error, match=code):
        verify_svg_bytes(mutated, evidence, enforce_exact_bytes=False)


@pytest.mark.parametrize(
    ("mutated", "code"),
    [
        (b'<!DOCTYPE svg SYSTEM "x">', "SVG_XML_PROLOG"),
        (b"<!ENTITY xxe '0'>", "SVG_XML_PROLOG"),
    ],
)
def test_rejects_hostile_xml_prolog(mutated: bytes, code: str) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()

    with pytest.raises(svg_contract_error, match=code):
        verify_svg_bytes(mutated + source, evidence, enforce_exact_bytes=False)


@pytest.mark.parametrize(
    ("needle", "replacement", "code"),
    [
        (b"</svg>", b"<style>svg{}</style></svg>", "SVG_ELEMENT"),
        (b"</svg>", b"<foreignObject></foreignObject></svg>", "SVG_ELEMENT"),
        (b"</svg>", b'<use href="#legend"></use></svg>', "SVG_ELEMENT"),
        (b'font-weight="700"', b'font-weight="700" onload="0"', "SVG_ATTR"),
        (b'font-size="16"', b'font-size="16" href="#legend"', "SVG_ATTR"),
        (b'fill="#2563eb"', b'fill="url(#legend)"', "SVG_VALUE"),
        (b'fill="#0f766e"', b'fill="data:image/png;base64,AA=="', "SVG_VALUE"),
        (
            b'font-family="Arial, sans-serif"',
            b'font-family="Remote, https://example.invalid/font.woff2"',
            "SVG_VALUE",
        ),
    ],
)
def test_rejects_disallowed_elements_attributes_and_values(
    needle: bytes,
    replacement: bytes,
    code: str,
) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()

    with pytest.raises(svg_contract_error, match=code):
        verify_svg_bytes(
            source.replace(needle, replacement, 1), evidence, enforce_exact_bytes=False
        )


@pytest.mark.parametrize(
    ("metric_index", "attribute_name"),
    [
        (0, "dice_mean"),
        (0, "iou_mean"),
        (1, "dice_mean"),
        (1, "iou_mean"),
    ],
)
def test_rejects_metric_token_drift(metric_index: int, attribute_name: str) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()
    expected_metric = getattr(evidence.rows[metric_index], attribute_name)
    expected_token = _decimal_token(expected_metric)
    mutated_token = _mutate_metric_token(expected_metric)

    assert mutated_token != expected_token
    mutated = source.replace(expected_token.encode("utf-8"), mutated_token.encode("utf-8"), 1)

    with pytest.raises(svg_contract_error, match="SVG_ROW_VALUE"):
        verify_svg_bytes(mutated, evidence, enforce_exact_bytes=False)


@pytest.mark.parametrize("attribute_name", ["dice_mean", "iou_mean"])
def test_rejects_swapped_metric_values_between_model_rows(attribute_name: str) -> None:
    svg_contract_error, _load_verified_svg, verify_svg_bytes, _module = _svg_exports()
    source, evidence = _approved_svg_bytes()
    first_token = _decimal_token(getattr(evidence.rows[0], attribute_name))
    second_token = _decimal_token(getattr(evidence.rows[1], attribute_name))

    assert first_token != second_token
    mutated = _swap_tokens(source, first_token, second_token)

    with pytest.raises(svg_contract_error, match="SVG_ROW_VALUE"):
        verify_svg_bytes(mutated, evidence, enforce_exact_bytes=False)
