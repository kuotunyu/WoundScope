"""Strict rendering for verified multi-seed full-run results."""

from __future__ import annotations

import math
import statistics
from typing import Any

import numpy as np

METRICS = ("dice", "iou", "precision", "recall", "specificity")


def validate_verified_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") != "completed":
        raise ValueError("Results status must be completed")
    if payload.get("run_mode") != "full" or payload.get("verified") is not True:
        raise ValueError("Only verified full-run results may update README")
    if payload.get("split") != "official_validation":
        raise ValueError("README results must use official_validation")
    experiments = payload.get("experiments")
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("Results must contain at least one experiment")
    for experiment in experiments:
        if sorted(experiment.get("seeds", [])) != [42, 43, 44]:
            raise ValueError("Every final experiment must aggregate seeds 42/43/44")
        per_seed = experiment.get("per_seed")
        if not isinstance(per_seed, list) or sorted(
            int(seed_report.get("seed", -1)) for seed_report in per_seed
        ) != [42, 43, 44]:
            raise ValueError("Every final experiment must include per-seed aggregate evidence")
        for metric in METRICS:
            values = experiment.get(metric)
            if not isinstance(values, dict) or not {"mean", "std"} <= values.keys():
                raise ValueError(f"Missing mean/std for {metric}")
            seed_values = [
                float(seed_report["image_summary"][metric]["mean"]) for seed_report in per_seed
            ]
            recomputed_mean = statistics.fmean(seed_values)
            recomputed_std = statistics.stdev(seed_values)
            if not math.isclose(
                float(values["mean"]), recomputed_mean, abs_tol=1e-12
            ) or not math.isclose(float(values["std"]), recomputed_std, abs_tol=1e-12):
                raise ValueError(
                    f"Published {metric} does not match recomputed per-seed aggregate evidence"
                )
        ci = experiment.get("bootstrap_95_ci", {}).get("dice")
        if not isinstance(ci, list) or len(ci) != 2:
            raise ValueError("Missing two-sided Dice bootstrap 95% CI")
        bootstrap = experiment.get("bootstrap", {})
        distribution = experiment.get("bootstrap_distribution", {}).get("dice")
        if (
            bootstrap.get("samples") != 2000
            or bootstrap.get("cluster") != "image"
            or bootstrap.get("method") != "percentile"
            or not isinstance(distribution, list)
            or len(distribution) != 2000
        ):
            raise ValueError("Missing 2,000-sample image-cluster bootstrap evidence")
        recomputed_ci = [
            float(np.quantile(distribution, 0.025)),
            float(np.quantile(distribution, 0.975)),
        ]
        if not all(
            math.isclose(float(value), expected, abs_tol=1e-12)
            for value, expected in zip(ci, recomputed_ci, strict=True)
        ):
            raise ValueError("Published bootstrap CI does not match safe distribution evidence")
    return experiments


def render_results_table(payload: dict[str, Any]) -> str:
    experiments = validate_verified_results(payload)
    lines = [
        "| Model | Loss | Seeds | Dice mean±SD (95% CI) | IoU | Precision | Recall | Specificity |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for experiment in experiments:
        formatted = {
            metric: f"{experiment[metric]['mean']:.4f}±{experiment[metric]['std']:.4f}"
            for metric in METRICS
        }
        low, high = experiment["bootstrap_95_ci"]["dice"]
        lines.append(
            f"| {experiment['model']} | {experiment['loss']} | 42/43/44 | "
            f"{formatted['dice']} ({low:.4f}–{high:.4f}) | {formatted['iou']} | "
            f"{formatted['precision']} | {formatted['recall']} | {formatted['specificity']} |"
        )
    return "\n".join(lines)


def replace_marker_region(readme: str, rendered_table: str) -> str:
    start = "<!-- RESULTS_TABLE_START -->"
    end = "<!-- RESULTS_TABLE_END -->"
    if readme.count(start) != 1 or readme.count(end) != 1:
        raise ValueError("README must contain exactly one results marker pair")
    prefix, remainder = readme.split(start, 1)
    _current, suffix = remainder.split(end, 1)
    return f"{prefix}{start}\n\n{rendered_table}\n\n{end}{suffix}"
