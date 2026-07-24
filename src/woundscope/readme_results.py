"""Strict rendering for verified multi-seed full-run results."""

from __future__ import annotations

from typing import Any

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
        for metric in METRICS:
            values = experiment.get(metric)
            if not isinstance(values, dict) or not {"mean", "std"} <= values.keys():
                raise ValueError(f"Missing mean/std for {metric}")
        ci = experiment.get("bootstrap_95_ci", {}).get("dice")
        if not isinstance(ci, list) or len(ci) != 2:
            raise ValueError("Missing two-sided Dice bootstrap 95% CI")
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
