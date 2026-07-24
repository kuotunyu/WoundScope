from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from woundscope.data_integrity import DataIntegrityError, validate_fuseg


def _write_image(path: Path, value: int, size: tuple[int, int] = (32, 32)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.full((size[1], size[0], 3), value, dtype=np.uint8)
    array[8:24, 8:24, 0] = min(255, value + 30)
    Image.fromarray(array, mode="RGB").save(path)


def _write_mask(
    path: Path, value: int = 255, size: tuple[int, int] = (32, 32), invalid: bool = False
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.zeros((size[1], size[0]), dtype=np.uint8)
    array[10:20, 10:20] = 7 if invalid else value
    Image.fromarray(array, mode="L").save(path)


def _valid_fixture(root: Path) -> Path:
    for index, value in enumerate((20, 80, 140), start=1):
        _write_image(root / "train" / "images" / f"t{index}.png", value)
        _write_mask(root / "train" / "labels" / f"t{index}.png")
    _write_image(root / "validation" / "images" / "v1.png", 190)
    _write_mask(root / "validation" / "labels" / "v1.png")
    _write_image(root / "test" / "images" / "x1.png", 230)
    return root


def test_valid_dataset_writes_manifest_and_split(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    manifest = tmp_path / "manifest.csv"

    summary = validate_fuseg(
        root,
        manifest,
        near_duplicate_hamming=0,
        expected_counts={"train": 3, "validation": 1, "test": 1},
    )

    assert summary["counts"] == {"test": 1, "train": 3, "validation": 1}
    assert summary["masks"] == {"train": 3, "validation": 1, "test": 0}
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["internal_split"] for row in rows} >= {
        "train",
        "dev",
        "official_validation",
        "official_test",
    }
    assert all(not Path(row["image_relpath"]).is_absolute() for row in rows)


def test_missing_mask_is_fatal(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    (root / "train" / "labels" / "t1.png").unlink()

    with pytest.raises(DataIntegrityError, match="validation failed") as error:
        validate_fuseg(root, tmp_path / "manifest.csv", near_duplicate_hamming=0)

    assert any("without masks" in issue for issue in error.value.issues)


def test_corrupt_image_is_fatal(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    (root / "train" / "images" / "t1.png").write_bytes(b"not an image")

    with pytest.raises(DataIntegrityError, match="Corrupt or unreadable"):
        validate_fuseg(root, tmp_path / "manifest.csv", near_duplicate_hamming=0)


def test_size_mismatch_is_fatal(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    _write_mask(root / "validation" / "labels" / "v1.png", size=(16, 16))

    with pytest.raises(DataIntegrityError) as error:
        validate_fuseg(root, tmp_path / "manifest.csv", near_duplicate_hamming=0)

    assert any("Size mismatch" in issue for issue in error.value.issues)


def test_invalid_mask_value_is_fatal(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    _write_mask(root / "train" / "labels" / "t2.png", invalid=True)

    with pytest.raises(DataIntegrityError) as error:
        validate_fuseg(root, tmp_path / "manifest.csv", near_duplicate_hamming=0)

    assert any("non-binary" in issue for issue in error.value.issues)


def test_antialiased_boundary_is_normalized_with_warning(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    path = root / "validation" / "labels" / "v1.png"
    array = np.zeros((32, 32), dtype=np.uint8)
    array[10:20, 10:20] = 255
    array[9, 10:20] = 32
    Image.fromarray(array, mode="L").save(path)

    summary = validate_fuseg(root, tmp_path / "manifest.csv", near_duplicate_hamming=0)

    assert summary["warnings"]
    assert "threshold 128" in summary["warnings"][0]


def test_exact_cross_split_duplicate_requires_acknowledgement(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    source = root / "train" / "images" / "t1.png"
    duplicate = root / "validation" / "images" / "v1.png"
    duplicate.write_bytes(source.read_bytes())

    with pytest.raises(DataIntegrityError) as error:
        validate_fuseg(root, tmp_path / "manifest.csv", near_duplicate_hamming=0)
    assert "Exact image duplicates exist across official splits" in error.value.issues

    summary = validate_fuseg(
        root,
        tmp_path / "allowed.csv",
        near_duplicate_hamming=0,
        allow_cross_split_exact=True,
    )
    assert summary["exact_cross_split"]


def test_internal_split_is_deterministic(tmp_path: Path) -> None:
    root = _valid_fixture(tmp_path / "challenge")
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"

    validate_fuseg(root, first, near_duplicate_hamming=0, seed=42)
    validate_fuseg(root, second, near_duplicate_hamming=0, seed=42)

    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
