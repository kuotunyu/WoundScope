from __future__ import annotations

import pytest

from woundscope.readme_results import render_results_table, replace_marker_region


def _payload() -> dict:
    metric = {"mean": 0.8, "std": 0.02}
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
