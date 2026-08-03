from __future__ import annotations

import pytest

from woundscope.readme_results import render_results_table, replace_marker_region


def _payload() -> dict:
    metric = {"mean": 0.8, "std": 0.02}
    seed_metric_values = (0.78, 0.8, 0.82)
    return {
        "status": "completed",
        "run_mode": "full",
        "verified": True,
        "split": "official_validation",
        "experiments": [
            {
                "model": "unet",
                "loss": "bce_dice",
                "seeds": [42, 43, 44],
                "dice": metric,
                "iou": metric,
                "precision": metric,
                "recall": metric,
                "specificity": metric,
                "bootstrap_95_ci": {"dice": [0.75, 0.84]},
                "bootstrap_distribution": {"dice": [0.75] * 1000 + [0.84] * 1000},
                "bootstrap": {"samples": 2000, "cluster": "image", "method": "percentile"},
                "per_seed": [
                    {
                        "seed": seed,
                        "image_summary": {
                            name: {"mean": value}
                            for name in ("dice", "iou", "precision", "recall", "specificity")
                        },
                    }
                    for seed, value in zip((42, 43, 44), seed_metric_values, strict=True)
                ],
            }
        ],
    }


def test_verified_results_render_and_replace_markers() -> None:
    table = render_results_table(_payload())
    readme = "before\n<!-- RESULTS_TABLE_START -->\nold\n<!-- RESULTS_TABLE_END -->\nafter\n"
    updated = replace_marker_region(readme, table)
    assert "0.8000±0.0200" in updated
    assert "old" not in updated


def test_quick_or_unverified_results_are_rejected() -> None:
    payload = _payload()
    payload["run_mode"] = "quick"
    with pytest.raises(ValueError, match="verified full-run"):
        render_results_table(payload)


def test_tampered_aggregate_is_rejected_against_per_seed_values() -> None:
    payload = _payload()
    payload["experiments"][0]["dice"]["mean"] = 0.9

    with pytest.raises(ValueError, match="does not match recomputed per-seed"):
        render_results_table(payload)


def test_tampered_bootstrap_ci_is_rejected_against_safe_distribution() -> None:
    payload = _payload()
    payload["experiments"][0]["bootstrap_95_ci"]["dice"] = [0.7, 0.9]

    with pytest.raises(ValueError, match="bootstrap CI does not match"):
        render_results_table(payload)
