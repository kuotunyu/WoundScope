"""FUSeg data discovery, integrity validation, duplicate grouping, and splitting."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
OFFICIAL_SPLITS = ("train", "validation", "test")


class DataIntegrityError(RuntimeError):
    """Raised when dataset structure or content is unsafe for training."""

    def __init__(self, message: str, issues: list[str] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or [message]


@dataclass
class ManifestRow:
    split: str
    sample_id: str
    image_relpath: str
    mask_relpath: str
    has_mask: bool
    width: int
    height: int
    channels: int
    mask_width: int | None
    mask_height: int | None
    mask_values: str
    foreground_pixels: int | None
    foreground_ratio: float | None
    image_sha256: str
    mask_sha256: str
    image_phash: str
    duplicate_group: str
    validation_status: str
    internal_split: str


class _UnionFind:
    def __init__(self, items: Iterable[int]) -> None:
        self.parent = {item: item for item in items}

    def find(self, item: int) -> int:
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            parent = self.parent[item]
            self.parent[item] = root
            item = parent
        return root

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def perceptual_hash(image: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """Compute a deterministic pHash without SciPy."""

    size = hash_size * highfreq_factor
    pixels = np.asarray(
        image.convert("L").resize((size, size), Image.Resampling.LANCZOS), dtype=np.float64
    )
    coordinates = np.arange(size, dtype=np.float64)
    frequencies = coordinates[:, None]
    basis = np.cos(math.pi * (2 * coordinates + 1) * frequencies / (2 * size))
    basis[0] *= 1 / math.sqrt(2)
    basis *= math.sqrt(2 / size)
    dct = basis @ pixels @ basis.T
    low = dct[:hash_size, :hash_size]
    median = float(np.median(low.flat[1:]))
    bits = (low > median).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    width = (hash_size * hash_size + 3) // 4
    return f"{value:0{width}x}"


def phash_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _list_images(path: Path) -> dict[str, Path]:
    if not path.is_dir():
        return {}
    result: dict[str, Path] = {}
    for candidate in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
        if not candidate.is_file() or candidate.suffix.casefold() not in SUPPORTED_SUFFIXES:
            continue
        key = candidate.stem.casefold()
        if key in result:
            raise DataIntegrityError(
                f"Duplicate case-insensitive sample stem in {path}: {candidate.stem}"
            )
        result[key] = candidate
    return result


def _load_image(path: Path, mode: str) -> Image.Image:
    try:
        with Image.open(path) as probe:
            probe.verify()
        with Image.open(path) as source:
            converted = source.convert(mode)
            converted.load()
            return converted.copy()
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise DataIntegrityError(f"Corrupt or unreadable image: {path}: {exc}") from exc


def _mask_metadata(mask: Image.Image, path: Path) -> tuple[str, int, float, str, str | None]:
    array = np.asarray(mask)
    values = sorted(int(value) for value in np.unique(array))
    status = "ok"
    warning: str | None = None
    if set(values).issubset({0, 1, 255}):
        binary = array > 0
    else:
        intermediate = (array != 0) & (array != 255)
        positive = array >= 128
        padded = np.pad(positive, 1, mode="constant", constant_values=False)
        adjacent_to_positive = np.zeros_like(positive, dtype=bool)
        for row_shift in range(3):
            for column_shift in range(3):
                adjacent_to_positive |= padded[
                    row_shift : row_shift + positive.shape[0],
                    column_shift : column_shift + positive.shape[1],
                ]
        intermediate_fraction = float(np.mean(intermediate))
        if intermediate_fraction > 0.01 or not np.all(adjacent_to_positive[intermediate]):
            raise DataIntegrityError(f"Mask contains non-binary values {values}: {path}")
        binary = positive
        status = "mask_antialias_normalized"
        warning = (
            f"Normalized anti-aliased mask boundary at threshold 128: {path.name}; "
            f"values={values}; intermediate_pixels={int(np.count_nonzero(intermediate))}"
        )
    foreground = int(np.count_nonzero(binary))
    ratio = foreground / int(binary.size)
    return "|".join(str(value) for value in values), foreground, ratio, status, warning


def _discover_pairs(
    challenge_dir: Path,
) -> tuple[list[tuple[str, str, Path, Path | None]], list[str]]:
    pairs: list[tuple[str, str, Path, Path | None]] = []
    issues: list[str] = []
    for split in OFFICIAL_SPLITS:
        split_dir = challenge_dir / split
        images = _list_images(split_dir / "images")
        masks = _list_images(split_dir / "labels")
        if not images:
            issues.append(f"No images found for official split: {split}")
            continue
        if split in {"train", "validation"}:
            missing_masks = sorted(set(images) - set(masks))
            orphan_masks = sorted(set(masks) - set(images))
            if missing_masks:
                issues.append(f"{split}: images without masks: {missing_masks[:10]}")
            if orphan_masks:
                issues.append(f"{split}: masks without images: {orphan_masks[:10]}")
        elif masks:
            issues.append("test: unexpected public masks are present")
        for key, image_path in images.items():
            pairs.append((split, image_path.stem, image_path, masks.get(key)))
    return pairs, issues


def _assign_duplicate_groups(
    rows: list[ManifestRow], near_duplicate_hamming: int
) -> dict[str, Any]:
    union = _UnionFind(range(len(rows)))
    by_sha: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_sha[row.image_sha256].append(index)
    for indices in by_sha.values():
        for other in indices[1:]:
            union.union(indices[0], other)

    near_pairs: list[tuple[int, int, int]] = []
    for left in range(len(rows)):
        for right in range(left + 1, len(rows)):
            if rows[left].image_sha256 == rows[right].image_sha256:
                continue
            distance = phash_distance(rows[left].image_phash, rows[right].image_phash)
            if distance <= near_duplicate_hamming:
                union.union(left, right)
                near_pairs.append((left, right, distance))

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        grouped[union.find(index)].append(index)
    ordered_groups = sorted(grouped.values(), key=lambda members: min(members))
    for group_number, members in enumerate(ordered_groups, start=1):
        group_id = f"dup-{group_number:04d}"
        for index in members:
            rows[index].duplicate_group = group_id

    exact_cross_split: list[dict[str, Any]] = []
    for sha, indices in sorted(by_sha.items()):
        splits = sorted({rows[index].split for index in indices})
        if len(splits) > 1:
            exact_cross_split.append(
                {
                    "sha256": sha,
                    "splits": splits,
                    "samples": [
                        f"{rows[index].split}/{rows[index].sample_id}" for index in indices
                    ],
                }
            )

    near_cross_split = [
        {
            "left": f"{rows[left].split}/{rows[left].sample_id}",
            "right": f"{rows[right].split}/{rows[right].sample_id}",
            "distance": distance,
        }
        for left, right, distance in near_pairs
        if rows[left].split != rows[right].split
    ]
    return {
        "duplicate_groups": sum(len(members) > 1 for members in ordered_groups),
        "exact_cross_split": exact_cross_split,
        "near_cross_split": near_cross_split,
    }


def _foreground_bin(value: float, edges: np.ndarray) -> int:
    return int(np.searchsorted(edges, value, side="right"))


def assign_internal_split(
    rows: list[ManifestRow], dev_fraction: float = 0.2, seed: int = 42
) -> None:
    """Create a deterministic, duplicate-group-aware foreground-stratified split."""

    train_indices = [index for index, row in enumerate(rows) if row.split == "train"]
    if not train_indices:
        return
    ratios = np.array([rows[index].foreground_ratio or 0.0 for index in train_indices])
    edges = np.unique(np.quantile(ratios, [0.2, 0.4, 0.6, 0.8]))
    grouped: dict[str, list[int]] = defaultdict(list)
    for index in train_indices:
        grouped[rows[index].duplicate_group].append(index)

    by_bin: dict[int, list[tuple[str, list[int]]]] = defaultdict(list)
    for group_id, indices in grouped.items():
        mean_ratio = float(np.mean([rows[index].foreground_ratio or 0.0 for index in indices]))
        by_bin[_foreground_bin(mean_ratio, edges)].append((group_id, indices))

    dev_indices: set[int] = set()
    for bin_id, groups in sorted(by_bin.items()):
        randomizer = random.Random(seed + bin_id)
        ordered = sorted(groups, key=lambda item: item[0])
        randomizer.shuffle(ordered)
        bin_count = sum(len(indices) for _, indices in ordered)
        target = max(1, round(bin_count * dev_fraction)) if len(ordered) > 1 else 0
        assigned = 0
        for _group_id, indices in ordered:
            if assigned >= target:
                break
            dev_indices.update(indices)
            assigned += len(indices)

    for index, row in enumerate(rows):
        if row.split == "train":
            row.internal_split = "dev" if index in dev_indices else "train"
        elif row.split == "validation":
            row.internal_split = "official_validation"
        else:
            row.internal_split = "official_test"


def _write_manifest(rows: list[ManifestRow], manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    temporary.replace(manifest_path)


def _write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def validate_fuseg(
    challenge_dir: str | Path,
    manifest_path: str | Path,
    *,
    near_duplicate_hamming: int = 4,
    dev_fraction: float = 0.2,
    seed: int = 42,
    expected_counts: dict[str, int] | None = None,
    allow_cross_split_exact: bool = False,
) -> dict[str, Any]:
    """Validate FUSeg and persist a portable image-level manifest plus aggregate summary."""

    challenge_dir = Path(challenge_dir).resolve()
    manifest_path = Path(manifest_path).resolve()
    pairs, structural_issues = _discover_pairs(challenge_dir)
    warnings: list[str] = []
    rows: list[ManifestRow] = []
    for split, sample_id, image_path, mask_path in pairs:
        image = _load_image(image_path, "RGB")
        mask_width: int | None = None
        mask_height: int | None = None
        mask_values = ""
        foreground_pixels: int | None = None
        foreground_ratio: float | None = None
        mask_sha = ""
        validation_status = "ok"
        if mask_path is not None:
            mask = _load_image(mask_path, "L")
            mask_width, mask_height = mask.size
            if mask.size != image.size:
                structural_issues.append(
                    f"Size mismatch {split}/{sample_id}: image={image.size}, mask={mask.size}"
                )
            try:
                (
                    mask_values,
                    foreground_pixels,
                    foreground_ratio,
                    validation_status,
                    mask_warning,
                ) = _mask_metadata(mask, mask_path)
                if mask_warning:
                    warnings.append(mask_warning)
            except DataIntegrityError as exc:
                structural_issues.extend(exc.issues)
            mask_sha = sha256_file(mask_path)
        rows.append(
            ManifestRow(
                split=split,
                sample_id=sample_id,
                image_relpath=image_path.relative_to(challenge_dir).as_posix(),
                mask_relpath=(mask_path.relative_to(challenge_dir).as_posix() if mask_path else ""),
                has_mask=mask_path is not None,
                width=image.width,
                height=image.height,
                channels=3,
                mask_width=mask_width,
                mask_height=mask_height,
                mask_values=mask_values,
                foreground_pixels=foreground_pixels,
                foreground_ratio=foreground_ratio,
                image_sha256=sha256_file(image_path),
                mask_sha256=mask_sha,
                image_phash=perceptual_hash(image),
                duplicate_group="",
                validation_status=validation_status,
                internal_split="",
            )
        )

    if not rows:
        raise DataIntegrityError(f"No FUSeg samples discovered under {challenge_dir}")
    duplicate_summary = _assign_duplicate_groups(rows, near_duplicate_hamming)
    assign_internal_split(rows, dev_fraction=dev_fraction, seed=seed)

    counts = Counter(row.split for row in rows)
    if expected_counts:
        for split, expected in expected_counts.items():
            actual = counts.get(split, 0)
            if actual != expected:
                structural_issues.append(
                    f"Unexpected {split} count: expected {expected}, found {actual}"
                )

    duplicate_members = Counter(row.duplicate_group for row in rows)
    for row in rows:
        if duplicate_members[row.duplicate_group] > 1:
            duplicate_status = "duplicate_or_near_duplicate"
            row.validation_status = (
                duplicate_status
                if row.validation_status == "ok"
                else f"{row.validation_status}|{duplicate_status}"
            )

    summary: dict[str, Any] = {
        "challenge_dir": str(challenge_dir),
        "manifest_path": str(manifest_path),
        "counts": dict(sorted(counts.items())),
        "internal_counts": dict(sorted(Counter(row.internal_split for row in rows).items())),
        "masks": {
            split: sum(row.has_mask for row in rows if row.split == split)
            for split in OFFICIAL_SPLITS
        },
        "structural_issues": structural_issues,
        "warnings": warnings,
        "cross_split_exact_acknowledged": bool(
            duplicate_summary["exact_cross_split"] and allow_cross_split_exact
        ),
        **duplicate_summary,
    }
    _write_manifest(rows, manifest_path)
    _write_json(summary, manifest_path.with_name("data_summary.json"))

    fatal_issues = list(structural_issues)
    if duplicate_summary["exact_cross_split"] and not allow_cross_split_exact:
        fatal_issues.append("Exact image duplicates exist across official splits")
    if fatal_issues:
        raise DataIntegrityError("FUSeg integrity validation failed", fatal_issues)
    return summary
