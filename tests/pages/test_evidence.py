from __future__ import annotations

import importlib
import re
import subprocess
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]

TAG_NAME = "v0.2.2"
TAG_OBJECT = "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4"
PEELED_COMMIT = "1b3df3b516cc4d366dc9da3cb01e8d0a319be613"
README_BLOB = "f5b8dd4681738aa372072cac9c827478d13c1f68"
DATA_CARD_BLOB = "2b7fe52ac9784c9c2682300d2bd56bb72b20d19c"
MODEL_CARD_BLOB = "c93a99579ad1b4fb1d03b0a6e15ba8300287ca9c"
SVG_BLOB = "28d91ba5f6fb61d1114106e7519007d6aeb5d6b8"
RESULTS_TABLE_START = b"<!-- RESULTS_TABLE_START -->"
RESULTS_TABLE_END = b"<!-- RESULTS_TABLE_END -->"
EXPECTED_COLUMNS = (
    "Model",
    "Loss",
    "Seeds",
    "Dice mean±SD (95% CI)",
    "IoU",
    "Precision",
    "Recall",
    "Specificity",
)
EXPECTED_MODELS = ("unet_efficientnet_b0", "segformer_b0")
EXPECTED_LOSS = "bce_dice"
EXPECTED_SEEDS = (42, 43, 44)
EXPECTED_VALIDATION_IMAGES = 200
EXPECTED_BOOTSTRAP_ITERATIONS = 2000

PAIR_RE = re.compile(
    r"^(?P<mean>\d+\.\d+)±(?P<sd>\d+\.\d+)(?: \((?P<low>\d+\.\d+)–(?P<high>\d+\.\d+)\))?$"
)


@dataclass(frozen=True, slots=True)
class ExpectedRow:
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


def _import_evidence_module():
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(REPOSITORY))
        return importlib.import_module("scripts.pages_site.evidence")
    finally:
        sys.path[:] = original_path


def _evidence_exports() -> tuple[type[Exception], object, object]:
    module = _import_evidence_module()
    return (module.EvidenceContractError, module.load_public_evidence, module.parse_results_table)


def _git_object(object_id: str, expected_type: str) -> bytes:
    object_type = subprocess.run(
        ["git", "cat-file", "-t", object_id],
        check=True,
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    assert object_type == expected_type
    return subprocess.run(
        ["git", "cat-file", "-p", object_id],
        check=True,
        cwd=REPOSITORY,
        capture_output=True,
    ).stdout


def _parse_decimal_pair(
    cell: str,
) -> tuple[Decimal, Decimal] | tuple[Decimal, Decimal, Decimal, Decimal]:
    match = PAIR_RE.fullmatch(cell)
    assert match is not None
    values = {
        name: Decimal(value) for name, value in match.groupdict().items() if value is not None
    }
    assert all(number.is_finite() for number in values.values())
    if {"low", "high"} <= values.keys():
        return values["mean"], values["sd"], values["low"], values["high"]
    return values["mean"], values["sd"]


def _extract_expected_rows(readme_bytes: bytes) -> tuple[ExpectedRow, ExpectedRow]:
    assert readme_bytes.count(RESULTS_TABLE_START) == 1
    assert readme_bytes.count(RESULTS_TABLE_END) == 1
    block = readme_bytes.split(RESULTS_TABLE_START, 1)[1].split(RESULTS_TABLE_END, 1)[0]
    lines = [line.strip() for line in block.decode("utf-8").splitlines() if line.strip()]
    assert len(lines) == 4
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    divider = [cell.strip() for cell in lines[1].strip("|").split("|")]
    assert tuple(header) == EXPECTED_COLUMNS
    assert len(header) == 8
    assert len(divider) == 8
    rows: list[ExpectedRow] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 8
        dice_mean, dice_sd, dice_ci_low, dice_ci_high = _parse_decimal_pair(cells[3])
        iou_mean, iou_sd = _parse_decimal_pair(cells[4])
        precision_mean, precision_sd = _parse_decimal_pair(cells[5])
        recall_mean, recall_sd = _parse_decimal_pair(cells[6])
        specificity_mean, specificity_sd = _parse_decimal_pair(cells[7])
        rows.append(
            ExpectedRow(
                model_id=cells[0],
                loss=cells[1],
                seeds=tuple(int(seed) for seed in cells[2].split("/")),
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
    assert tuple(row.model_id for row in rows) == EXPECTED_MODELS
    assert len({row.model_id for row in rows}) == len(rows)
    assert all(row.loss == EXPECTED_LOSS for row in rows)
    assert all(row.seeds == EXPECTED_SEEDS for row in rows)
    return tuple(rows)


def test_loads_exact_release_objects_and_two_models() -> None:
    _evidence_contract_error, load_public_evidence, _parse_results_table = _evidence_exports()
    readme_bytes = _git_object(README_BLOB, "blob")
    expected_rows = _extract_expected_rows(readme_bytes)
    evidence = load_public_evidence(REPOSITORY)

    assert evidence.provenance.tag_name == TAG_NAME
    assert evidence.provenance.tag_object == TAG_OBJECT
    assert evidence.provenance.peeled_commit == PEELED_COMMIT
    assert evidence.provenance.readme_blob == README_BLOB
    assert evidence.provenance.data_card_blob == DATA_CARD_BLOB
    assert evidence.provenance.model_card_blob == MODEL_CARD_BLOB
    assert evidence.provenance.svg_blob == SVG_BLOB
    assert evidence.validation_images == EXPECTED_VALIDATION_IMAGES
    assert evidence.bootstrap_iterations == EXPECTED_BOOTSTRAP_ITERATIONS
    assert evidence.readme_bytes == readme_bytes
    assert [row.model_id for row in evidence.rows] == list(EXPECTED_MODELS)
    assert all(row.loss == EXPECTED_LOSS and row.seeds == EXPECTED_SEEDS for row in evidence.rows)
    assert len(evidence.rows) == 2
    for row, expected in zip(evidence.rows, expected_rows, strict=True):
        assert row.model_id == expected.model_id
        assert row.loss == expected.loss
        assert row.seeds == expected.seeds
        assert row.dice_mean == expected.dice_mean
        assert row.dice_sd == expected.dice_sd
        assert row.dice_ci_low == expected.dice_ci_low
        assert row.dice_ci_high == expected.dice_ci_high
        assert row.iou_mean == expected.iou_mean
        assert row.iou_sd == expected.iou_sd
        assert row.precision_mean == expected.precision_mean
        assert row.precision_sd == expected.precision_sd
        assert row.recall_mean == expected.recall_mean
        assert row.recall_sd == expected.recall_sd
        assert row.specificity_mean == expected.specificity_mean
        assert row.specificity_sd == expected.specificity_sd
        assert all(
            value.is_finite()
            for value in (
                row.dice_mean,
                row.dice_sd,
                row.dice_ci_low,
                row.dice_ci_high,
                row.iou_mean,
                row.iou_sd,
                row.precision_mean,
                row.precision_sd,
                row.recall_mean,
                row.recall_sd,
                row.specificity_mean,
                row.specificity_sd,
            )
        )


def test_rejects_duplicate_result_markers() -> None:
    evidence_contract_error, _load_public_evidence, parse_results_table = _evidence_exports()
    readme = _git_object(README_BLOB, "blob")
    with pytest.raises(evidence_contract_error, match="RESULT_MARKER_COUNT"):
        parse_results_table(readme + b"\n<!-- RESULTS_TABLE_START -->\n")


def test_repo_root_python_imports_pages_site_module_without_installing_wheel() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import scripts.pages_site.evidence"],
        check=False,
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""


def test_rejects_tag_ref_pointing_to_different_annotated_tag_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _import_evidence_module()
    readme = _git_object(README_BLOB, "blob")
    tag_bytes = _git_object(TAG_OBJECT, "tag")
    other_tag_object = "9" * 40

    def fake_run_git(repository: Path, arguments: list[str]) -> bytes:
        if arguments == ["rev-parse", f"refs/tags/{TAG_NAME}^{{tag}}"]:
            return f"{other_tag_object}\n".encode()
        if arguments == ["rev-parse", f"{TAG_NAME}^{{}}"]:
            return f"{PEELED_COMMIT}\n".encode()
        raise AssertionError(arguments)

    def fake_read_git_object(repository: Path, object_id: str, expected_type: str) -> bytes:
        assert repository == REPOSITORY
        assert object_id == TAG_OBJECT
        assert expected_type == "tag"
        return tag_bytes

    def fake_read_commit_blob(
        repository: Path, commit_id: str, public_path: str, expected_blob: str
    ) -> bytes:
        assert repository == REPOSITORY
        assert commit_id == PEELED_COMMIT
        if public_path == module.README_PATH:
            return readme
        return b"public"

    monkeypatch.setattr(module, "_run_git", fake_run_git)
    monkeypatch.setattr(module, "read_git_object", fake_read_git_object)
    monkeypatch.setattr(module, "_read_commit_blob", fake_read_commit_blob)

    with pytest.raises(module.EvidenceContractError, match="TAG_REF_MISMATCH"):
        module.load_public_evidence(REPOSITORY)


def test_rejects_dice_cell_without_required_ci() -> None:
    evidence_contract_error, _load_public_evidence, parse_results_table = _evidence_exports()
    readme_text = _git_object(README_BLOB, "blob").decode("utf-8")
    mutated = re.sub(
        r"(?P<prefix>\| unet_efficientnet_b0 \| bce_dice \| 42/43/44 \| \d+\.\d+±\d+\.\d+) "
        r"\(\d+\.\d+–\d+\.\d+\)",
        r"\g<prefix>",
        readme_text,
        count=1,
    )

    assert mutated != readme_text
    with pytest.raises(evidence_contract_error, match="DICE_ARITY_INVALID"):
        parse_results_table(mutated.encode("utf-8"))


@pytest.mark.parametrize(
    ("metric_name", "cell_pattern", "replacement", "expected_code"),
    (
        (
            "IoU",
            r"(?P<value>\d+\.\d+±\d+\.\d+)",
            r"\g<value> (0.1111–0.2222)",
            "IOU_ARITY_INVALID",
        ),
        (
            "Precision",
            r"(?P<value>\d+\.\d+±\d+\.\d+)",
            r"\g<value> (0.1111–0.2222)",
            "PRECISION_ARITY_INVALID",
        ),
        (
            "Recall",
            r"(?P<value>\d+\.\d+±\d+\.\d+)",
            r"\g<value> (0.1111–0.2222)",
            "RECALL_ARITY_INVALID",
        ),
        (
            "Specificity",
            r"(?P<value>\d+\.\d+±\d+\.\d+)",
            r"\g<value> (0.1111–0.2222)",
            "SPECIFICITY_ARITY_INVALID",
        ),
    ),
)
def test_rejects_non_dice_metric_with_ci_suffix(
    metric_name: str,
    cell_pattern: str,
    replacement: str,
    expected_code: str,
) -> None:
    evidence_contract_error, _load_public_evidence, parse_results_table = _evidence_exports()
    readme_text = _git_object(README_BLOB, "blob").decode("utf-8")
    column_prefixes = {
        "IoU": (
            r"(?P<prefix>\| unet_efficientnet_b0 \| bce_dice \| 42/43/44 \| "
            r"\d+\.\d+±\d+\.\d+ \(\d+\.\d+–\d+\.\d+\) \| )"
        ),
        "Precision": (
            r"(?P<prefix>\| unet_efficientnet_b0 \| bce_dice \| 42/43/44 \| "
            r"\d+\.\d+±\d+\.\d+ \(\d+\.\d+–\d+\.\d+\) \| \d+\.\d+±\d+\.\d+ \| )"
        ),
        "Recall": (
            r"(?P<prefix>\| unet_efficientnet_b0 \| bce_dice \| 42/43/44 \| "
            r"\d+\.\d+±\d+\.\d+ \(\d+\.\d+–\d+\.\d+\) \| \d+\.\d+±\d+\.\d+ \| "
            r"\d+\.\d+±\d+\.\d+ \| )"
        ),
        "Specificity": (
            r"(?P<prefix>\| unet_efficientnet_b0 \| bce_dice \| 42/43/44 \| "
            r"\d+\.\d+±\d+\.\d+ \(\d+\.\d+–\d+\.\d+\) \| \d+\.\d+±\d+\.\d+ \| "
            r"\d+\.\d+±\d+\.\d+ \| \d+\.\d+±\d+\.\d+ \| )"
        ),
    }
    mutated = re.sub(
        f"{column_prefixes[metric_name]}{cell_pattern}(?P<suffix> \\|)",
        rf"\g<prefix>{replacement}\g<suffix>",
        readme_text,
        count=1,
    )

    assert mutated != readme_text
    with pytest.raises(evidence_contract_error, match=expected_code):
        parse_results_table(mutated.encode("utf-8"))
