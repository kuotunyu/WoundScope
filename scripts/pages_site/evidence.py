"""Load immutable public Pages evidence from pinned Git objects."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .constants import (
    DATA_CARD_BLOB,
    DATA_CARD_PATH,
    EXPECTED_COLUMNS,
    EXPECTED_LOSS,
    EXPECTED_MODEL_IDS,
    EXPECTED_SEEDS,
    EXPECTED_TAGGER,
    MODEL_CARD_BLOB,
    MODEL_CARD_PATH,
    PEELED_COMMIT,
    README_BLOB,
    README_PATH,
    RESULTS_TABLE_END,
    RESULTS_TABLE_START,
    SVG_BLOB,
    SVG_PATH,
    TAG_NAME,
    TAG_OBJECT,
    TAG_REF,
)

_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_RESULT_RE = re.compile(
    r"^(?P<mean>\d+\.\d+)±(?P<sd>\d+\.\d+)(?: \((?P<low>\d+\.\d+)–(?P<high>\d+\.\d+)\))?$"
)
_VALIDATION_IMAGES_RE = re.compile(r"完整\s*(?P<count>\d+)\s*張評估證據")
_BOOTSTRAP_ITERATIONS_RE = re.compile(r"(?P<count>\d{1,3}(?:,\d{3})*)\s*次 image-level Bootstrap")


class EvidenceContractError(RuntimeError):
    """Stable, public-safe contract failure."""

    def __init__(self, code: str, public_path: str | None = None) -> None:
        self.code = code
        self.public_path = public_path
        message = code if public_path is None else f"{code}:{public_path}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    tag_name: str
    tag_object: str
    peeled_commit: str
    readme_blob: str
    data_card_blob: str
    model_card_blob: str
    svg_blob: str


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    model_id: str
    loss: str
    seeds: tuple[int, int, int]
    dice_mean: Decimal
    dice_sd: Decimal
    dice_ci_low: Decimal
    dice_ci_high: Decimal
    iou_mean: Decimal
    iou_sd: Decimal
    precision_mean: Decimal
    precision_sd: Decimal
    recall_mean: Decimal
    recall_sd: Decimal
    specificity_mean: Decimal
    specificity_sd: Decimal


@dataclass(frozen=True, slots=True)
class PublicEvidence:
    provenance: EvidenceProvenance
    rows: tuple[EvidenceRow, EvidenceRow]
    validation_images: int
    bootstrap_iterations: int
    readme_bytes: bytes


def _run_git(repository: Path, arguments: list[str]) -> bytes:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        raise EvidenceContractError("GIT_COMMAND_FAILED") from error


def _decode_utf8(payload: bytes, *, code: str, public_path: str | None = None) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise EvidenceContractError(code, public_path=public_path) from error


def _require_hex40(value: str, *, code: str) -> str:
    if _HEX40_RE.fullmatch(value) is None:
        raise EvidenceContractError(code)
    return value


def read_git_object(repository: Path, object_id: str, expected_type: str) -> bytes:
    _require_hex40(object_id, code="OBJECT_ID_INVALID")
    object_type = _decode_utf8(
        _run_git(repository, ["cat-file", "-t", object_id]), code="OBJECT_TYPE_INVALID"
    )
    if object_type.strip() != expected_type:
        raise EvidenceContractError("OBJECT_TYPE_MISMATCH")
    return _run_git(repository, ["cat-file", "-p", object_id])


def _read_commit_blob(
    repository: Path, commit_id: str, public_path: str, expected_blob: str
) -> bytes:
    output = _decode_utf8(
        _run_git(repository, ["ls-tree", commit_id, "--", public_path]),
        code="TREE_ENTRY_INVALID",
        public_path=public_path,
    ).strip()
    if not output:
        raise EvidenceContractError("TREE_ENTRY_MISSING", public_path=public_path)
    parts = output.split(maxsplit=3)
    if len(parts) != 4:
        raise EvidenceContractError("TREE_ENTRY_INVALID", public_path=public_path)
    _mode, entry_type, object_id, returned_path = parts
    if entry_type != "blob" or returned_path != public_path:
        raise EvidenceContractError("TREE_ENTRY_INVALID", public_path=public_path)
    if object_id != expected_blob:
        raise EvidenceContractError("BLOB_LOCK_MISMATCH", public_path=public_path)
    return read_git_object(repository, object_id, "blob")


def _parse_metric(
    cell: str,
    *,
    code: str,
    arity_code: str,
    require_ci: bool,
) -> tuple[Decimal, Decimal] | tuple[Decimal, Decimal, Decimal, Decimal]:
    match = _RESULT_RE.fullmatch(cell)
    if match is None:
        raise EvidenceContractError(code)
    values: dict[str, Decimal] = {}
    for key, raw_value in match.groupdict().items():
        if raw_value is None:
            continue
        try:
            value = Decimal(raw_value)
        except InvalidOperation as error:
            raise EvidenceContractError(code) from error
        if not value.is_finite():
            raise EvidenceContractError(code)
        values[key] = value
    has_ci = "low" in values and "high" in values
    if has_ci != require_ci:
        raise EvidenceContractError(arity_code, public_path=README_PATH)
    if has_ci:
        return values["mean"], values["sd"], values["low"], values["high"]
    return values["mean"], values["sd"]


def parse_results_table(readme_bytes: bytes) -> tuple[EvidenceRow, EvidenceRow]:
    start_count = readme_bytes.count(RESULTS_TABLE_START)
    end_count = readme_bytes.count(RESULTS_TABLE_END)
    if start_count != 1 or end_count != 1:
        raise EvidenceContractError("RESULT_MARKER_COUNT", public_path=README_PATH)
    if readme_bytes.index(RESULTS_TABLE_START) > readme_bytes.index(RESULTS_TABLE_END):
        raise EvidenceContractError("RESULT_MARKER_ORDER", public_path=README_PATH)
    block = readme_bytes.split(RESULTS_TABLE_START, 1)[1].split(RESULTS_TABLE_END, 1)[0]
    decoded = _decode_utf8(block, code="README_UTF8_INVALID", public_path=README_PATH)
    lines = [line.strip() for line in decoded.splitlines() if line.strip()]
    if len(lines) != 4:
        raise EvidenceContractError("RESULT_ROW_COUNT", public_path=README_PATH)

    rows: list[list[str]] = []
    for line in lines:
        if not line.startswith("|") or not line.endswith("|"):
            raise EvidenceContractError("RESULT_TABLE_PIPES", public_path=README_PATH)
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(EXPECTED_COLUMNS):
            raise EvidenceContractError("RESULT_COLUMN_COUNT", public_path=README_PATH)
        rows.append(cells)

    header, divider, *body = rows
    if tuple(header) != EXPECTED_COLUMNS:
        raise EvidenceContractError("RESULT_HEADER_MISMATCH", public_path=README_PATH)
    if any(not cell for cell in divider):
        raise EvidenceContractError("RESULT_DIVIDER_INVALID", public_path=README_PATH)
    if len(body) != len(EXPECTED_MODEL_IDS):
        raise EvidenceContractError("RESULT_ROW_COUNT", public_path=README_PATH)

    parsed_rows: list[EvidenceRow] = []
    seen_models: set[str] = set()
    for index, cells in enumerate(body):
        model_id = cells[0]
        if model_id != EXPECTED_MODEL_IDS[index]:
            raise EvidenceContractError("MODEL_ID_MISMATCH", public_path=README_PATH)
        if model_id in seen_models:
            raise EvidenceContractError("MODEL_ID_DUPLICATE", public_path=README_PATH)
        seen_models.add(model_id)
        if cells[1] != EXPECTED_LOSS:
            raise EvidenceContractError("LOSS_MISMATCH", public_path=README_PATH)
        try:
            seeds = tuple(int(seed) for seed in cells[2].split("/"))
        except ValueError as error:
            raise EvidenceContractError("SEEDS_INVALID", public_path=README_PATH) from error
        if seeds != EXPECTED_SEEDS:
            raise EvidenceContractError("SEEDS_MISMATCH", public_path=README_PATH)
        dice_mean, dice_sd, dice_ci_low, dice_ci_high = _parse_metric(
            cells[3],
            code="DICE_INVALID",
            arity_code="DICE_ARITY_INVALID",
            require_ci=True,
        )
        iou_mean, iou_sd = _parse_metric(
            cells[4],
            code="IOU_INVALID",
            arity_code="IOU_ARITY_INVALID",
            require_ci=False,
        )
        precision_mean, precision_sd = _parse_metric(
            cells[5],
            code="PRECISION_INVALID",
            arity_code="PRECISION_ARITY_INVALID",
            require_ci=False,
        )
        recall_mean, recall_sd = _parse_metric(
            cells[6],
            code="RECALL_INVALID",
            arity_code="RECALL_ARITY_INVALID",
            require_ci=False,
        )
        specificity_mean, specificity_sd = _parse_metric(
            cells[7],
            code="SPECIFICITY_INVALID",
            arity_code="SPECIFICITY_ARITY_INVALID",
            require_ci=False,
        )
        parsed_rows.append(
            EvidenceRow(
                model_id=model_id,
                loss=cells[1],
                seeds=seeds,
                dice_mean=dice_mean,
                dice_sd=dice_sd,
                dice_ci_low=dice_ci_low,
                dice_ci_high=dice_ci_high,
                iou_mean=iou_mean,
                iou_sd=iou_sd,
                precision_mean=precision_mean,
                precision_sd=precision_sd,
                recall_mean=recall_mean,
                recall_sd=recall_sd,
                specificity_mean=specificity_mean,
                specificity_sd=specificity_sd,
            )
        )
    return parsed_rows[0], parsed_rows[1]


def _parse_validation_images(readme_text: str) -> int:
    match = _VALIDATION_IMAGES_RE.search(readme_text)
    if match is None:
        raise EvidenceContractError("VALIDATION_IMAGES_MISSING", public_path=README_PATH)
    return int(match.group("count"))


def _parse_bootstrap_iterations(readme_text: str) -> int:
    match = _BOOTSTRAP_ITERATIONS_RE.search(readme_text)
    if match is None:
        raise EvidenceContractError("BOOTSTRAP_ITERATIONS_MISSING", public_path=README_PATH)
    return int(match.group("count").replace(",", ""))


def load_public_evidence(repository: Path) -> PublicEvidence:
    tag_bytes = read_git_object(repository, TAG_OBJECT, "tag")
    tag_text = _decode_utf8(tag_bytes, code="TAG_UTF8_INVALID")
    lines = tag_text.splitlines()
    header_lines: list[str] = []
    for line in lines:
        if line == "":
            break
        header_lines.append(line)
    if len(header_lines) < 4:
        raise EvidenceContractError("TAG_PAYLOAD_INVALID")
    if header_lines[0] != f"object {PEELED_COMMIT}":
        raise EvidenceContractError("TAG_OBJECT_MISMATCH")
    if header_lines[1] != "type commit":
        raise EvidenceContractError("TAG_TARGET_TYPE_MISMATCH")
    if header_lines[2] != f"tag {TAG_NAME}":
        raise EvidenceContractError("TAG_NAME_MISMATCH")
    if not header_lines[3].startswith("tagger "):
        raise EvidenceContractError("TAG_TAGGER_MISSING")
    tagger = header_lines[3][len("tagger ") :].rsplit(" ", maxsplit=2)[0]
    if tagger != EXPECTED_TAGGER:
        raise EvidenceContractError("TAG_TAGGER_MISMATCH")

    resolved_tag_object = _decode_utf8(
        _run_git(repository, ["rev-parse", f"{TAG_REF}^{{tag}}"]),
        code="TAG_REF_INVALID",
    ).strip()
    if _require_hex40(resolved_tag_object, code="TAG_REF_INVALID") != TAG_OBJECT:
        raise EvidenceContractError("TAG_REF_MISMATCH")

    peeled_commit = _decode_utf8(
        _run_git(repository, ["rev-parse", f"{TAG_NAME}^{{}}"]), code="PEELED_COMMIT_INVALID"
    ).strip()
    if _require_hex40(peeled_commit, code="PEELED_COMMIT_INVALID") != PEELED_COMMIT:
        raise EvidenceContractError("PEELED_COMMIT_MISMATCH")

    readme_bytes = _read_commit_blob(repository, PEELED_COMMIT, README_PATH, README_BLOB)
    _read_commit_blob(repository, PEELED_COMMIT, DATA_CARD_PATH, DATA_CARD_BLOB)
    _read_commit_blob(repository, PEELED_COMMIT, MODEL_CARD_PATH, MODEL_CARD_BLOB)
    _read_commit_blob(repository, PEELED_COMMIT, SVG_PATH, SVG_BLOB)

    rows = parse_results_table(readme_bytes)
    readme_text = _decode_utf8(readme_bytes, code="README_UTF8_INVALID", public_path=README_PATH)
    return PublicEvidence(
        provenance=EvidenceProvenance(
            tag_name=TAG_NAME,
            tag_object=TAG_OBJECT,
            peeled_commit=PEELED_COMMIT,
            readme_blob=README_BLOB,
            data_card_blob=DATA_CARD_BLOB,
            model_card_blob=MODEL_CARD_BLOB,
            svg_blob=SVG_BLOB,
        ),
        rows=rows,
        validation_images=_parse_validation_images(readme_text),
        bootstrap_iterations=_parse_bootstrap_iterations(readme_text),
        readme_bytes=readme_bytes,
    )
