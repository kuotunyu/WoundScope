"""Recompute de-identified multi-seed official-validation aggregates."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

from woundscope.metrics import Confusion, metrics_from_confusion

METRICS = ("dice", "iou", "precision", "recall", "specificity")


def _as_confusion(payload: dict[str, Any]) -> Confusion:
    confusion = Confusion(
        true_positive=int(payload["true_positive"]),
        false_positive=int(payload["false_positive"]),
        false_negative=int(payload["false_negative"]),
        true_negative=int(payload["true_negative"]),
    )
    if any(value < 0 for value in vars(confusion).values()):
        raise ValueError("Confusion counts cannot be negative")
    return confusion


def _sum_confusions(confusions: list[Confusion]) -> Confusion:
    total = Confusion(0, 0, 0, 0)
    for confusion in confusions:
        total += confusion
    return total


def _summarize_image_confusions(confusions: list[Confusion]) -> dict[str, dict[str, float]]:
    image_metrics = [metrics_from_confusion(confusion) for confusion in confusions]
    summary: dict[str, dict[str, float]] = {}
    for metric in METRICS:
        values = np.asarray([row[metric] for row in image_metrics], dtype=np.float64)
        q1 = float(np.quantile(values, 0.25))
        q3 = float(np.quantile(values, 0.75))
        summary[metric] = {
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            "q1": q1,
            "q3": q3,
            "iqr": q3 - q1,
        }
    return summary


def _require_hash(value: object, length: int, label: str) -> str:
    normalized = str(value)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", normalized) is None:
        raise ValueError(f"Invalid {label}")
    return normalized


def attach_seed_report_metadata(
    report: dict[str, Any],
    *,
    config: dict[str, Any],
    provenance: dict[str, Any],
    split: str,
    checkpoint_sha256: str,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    """Attach frozen training identity to one private per-seed evaluation report."""

    if split not in {"dev", "official_validation"}:
        raise ValueError(f"Unsupported evaluation split: {split}")
    enriched = dict(report)
    enriched.update(
        {
            "model": str(config["model"]["name"]),
            "loss": str(config["training"]["loss"]),
            "seed": int(config["project"]["seed"]),
            "split": split,
            "source_commit": _require_hash(provenance.get("source_commit"), 40, "source_commit"),
            "config_sha256": _require_hash(provenance.get("config_sha256"), 64, "config_sha256"),
            "manifest_sha256": _require_hash(
                provenance.get("manifest_sha256"), 64, "manifest_sha256"
            ),
            "checkpoint_sha256": _require_hash(checkpoint_sha256, 64, "checkpoint_sha256"),
            "training_environment": {
                "packages": dict(provenance.get("packages", {})),
                "cuda_version": provenance.get("cuda_version"),
                "cudnn_version": provenance.get("cudnn_version"),
            },
            "bootstrap": {
                "samples": bootstrap_samples,
                "seed": bootstrap_seed,
                "cluster": "image",
            },
        }
    )
    return enriched


def aggregate_official_validation(
    reports: list[dict[str, Any]],
    *,
    bootstrap_samples: int = 2000,
    bootstrap_seed: int = 42,
) -> dict[str, Any]:
    """Recompute all public values from three frozen per-image confusion sets."""

    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")
    if sorted(int(report.get("seed", -1)) for report in reports) != [42, 43, 44]:
        raise ValueError("Official validation aggregation requires seeds 42/43/44 exactly once")
    reports = sorted(reports, key=lambda report: int(report["seed"]))
    for field in ("model", "loss", "source_commit", "manifest_sha256", "sample_order_sha256"):
        values = {str(report.get(field)) for report in reports}
        if len(values) != 1:
            raise ValueError(f"Per-seed reports have incompatible {field}")
    if any(
        report.get("status") != "completed" or report.get("split") != "official_validation"
        for report in reports
    ):
        raise ValueError("Only completed official_validation reports may be aggregated")

    source_commit = _require_hash(reports[0]["source_commit"], 40, "source_commit")
    manifest_sha256 = _require_hash(reports[0]["manifest_sha256"], 64, "manifest_sha256")
    sample_order_sha256 = _require_hash(
        reports[0]["sample_order_sha256"], 64, "sample_order_sha256"
    )
    seed_confusions: list[list[Confusion]] = []
    per_seed: list[dict[str, Any]] = []
    expected_image_count: int | None = None
    for report in reports:
        config_sha256 = _require_hash(report["config_sha256"], 64, "config_sha256")
        checkpoint_sha256 = _require_hash(report["checkpoint_sha256"], 64, "checkpoint_sha256")
        if report.get("calibration", {}).get("source_split") != "dev":
            raise ValueError("Official validation requires frozen internal-dev calibration")
        confusions = [_as_confusion(payload) for payload in report.get("confusions", [])]
        if not confusions:
            raise ValueError("Per-seed report has no image-level confusion evidence")
        if expected_image_count is None:
            expected_image_count = len(confusions)
        elif len(confusions) != expected_image_count:
            raise ValueError("Per-seed reports have different image counts")
        image_summary = _summarize_image_confusions(confusions)
        global_metrics = metrics_from_confusion(_sum_confusions(confusions))
        seed_confusions.append(confusions)
        per_seed.append(
            {
                "seed": int(report["seed"]),
                "image_count": len(confusions),
                "image_summary": image_summary,
                "global_metrics": global_metrics,
                "calibration": dict(report["calibration"]),
                "confidence": dict(report["confidence"]),
                "config_sha256": config_sha256,
                "checkpoint_sha256": checkpoint_sha256,
            }
        )

    aggregate_metrics: dict[str, dict[str, Any]] = {}
    for metric in METRICS:
        seed_values = [seed_report["image_summary"][metric]["mean"] for seed_report in per_seed]
        aggregate_metrics[metric] = {
            "mean": float(np.mean(seed_values)),
            "std": float(np.std(seed_values, ddof=1)),
            "ddof": 1,
            "seed_values": seed_values,
        }
        if not all(
            math.isfinite(value)
            for value in aggregate_metrics[metric].values()
            if not isinstance(value, list)
        ):
            raise ValueError(f"Non-finite aggregate metric: {metric}")

    randomizer = np.random.default_rng(bootstrap_seed)
    bootstrap_distributions = {metric: [] for metric in METRICS}
    for _ in range(bootstrap_samples):
        indices = randomizer.integers(0, expected_image_count, size=expected_image_count)
        for metric in METRICS:
            seed_means = []
            for confusions in seed_confusions:
                values = [
                    metrics_from_confusion(confusions[int(index)])[metric] for index in indices
                ]
                seed_means.append(float(np.mean(values)))
            bootstrap_distributions[metric].append(float(np.mean(seed_means)))
    bootstrap_95_ci = {
        metric: [
            float(np.quantile(values, 0.025)),
            float(np.quantile(values, 0.975)),
        ]
        for metric, values in bootstrap_distributions.items()
    }

    return {
        "model": str(reports[0]["model"]),
        "loss": str(reports[0]["loss"]),
        "seeds": [42, 43, 44],
        "source_commit": source_commit,
        "manifest_sha256": manifest_sha256,
        "sample_order_sha256": sample_order_sha256,
        "per_seed": per_seed,
        **aggregate_metrics,
        "bootstrap_95_ci": bootstrap_95_ci,
        "bootstrap_distribution": bootstrap_distributions,
        "bootstrap": {
            "samples": bootstrap_samples,
            "seed": bootstrap_seed,
            "cluster": "image",
            "method": "percentile",
            "confidence_level": 0.95,
        },
    }
