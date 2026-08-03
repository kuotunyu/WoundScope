from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from woundscope.orchestration import STAGE_ORDER, build_comparison_specs, build_quick_specs


def _module():
    return importlib.import_module("woundscope.colab_pipeline")


def test_pipeline_runs_stages_in_order_and_skips_hash_valid_completed_stages(
    tmp_path: Path,
) -> None:
    pipeline = _module()
    paths = pipeline.PipelinePaths(
        project_root=tmp_path / "project",
        data_root=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
    )
    paths.project_root.mkdir()
    calls: list[str] = []

    def handler(context):
        calls.append(context.stage)
        marker = paths.artifact_root / "stage_markers" / f"{context.stage}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f'{{"stage": "{context.stage}"}}', encoding="utf-8")
        return pipeline.StageOutcome(artifacts=[marker], evidence={"stage": context.stage})

    handlers = {stage: handler for stage in STAGE_ORDER}
    state = pipeline.run_pipeline(
        paths,
        source_commit="a" * 40,
        stage_handlers=handlers,
        cuda_probe=lambda: {"available": True, "device_name": "Synthetic CUDA"},
    )

    assert calls == list(STAGE_ORDER)
    assert list(state.stages) == list(STAGE_ORDER)
    assert all(stage["status"] == "completed" for stage in state.stages.values())

    calls.clear()
    resumed = pipeline.run_pipeline(
        paths,
        source_commit="a" * 40,
        stage_handlers=handlers,
        cuda_probe=lambda: {"available": True, "device_name": "Synthetic CUDA"},
    )
    assert calls == []
    assert resumed.stages == state.stages


def test_pipeline_refuses_cpu_before_any_stage(tmp_path: Path) -> None:
    pipeline = _module()
    paths = pipeline.PipelinePaths(tmp_path, tmp_path / "data", tmp_path / "artifacts")
    called = False

    def handler(_context):
        nonlocal called
        called = True
        raise AssertionError("stage should not execute")

    with pytest.raises(RuntimeError, match="CUDA"):
        pipeline.run_pipeline(
            paths,
            source_commit="a" * 40,
            stage_handlers={stage: handler for stage in STAGE_ORDER},
            cuda_probe=lambda: {"available": False},
        )
    assert called is False


def test_quick_train_plan_forces_resume_but_full_plan_does_not_interrupt(
    tmp_path: Path,
) -> None:
    pipeline = _module()
    quick_commands = pipeline.build_train_commands(build_quick_specs()[0], tmp_path / "quick")
    comparison_commands = pipeline.build_train_commands(
        build_comparison_specs()[0], tmp_path / "comparison"
    )

    assert len(quick_commands) == 2
    assert "--stop-after-epoch" in quick_commands[0]
    assert quick_commands[0][quick_commands[0].index("--stop-after-epoch") + 1] == "1"
    assert "--resume" in quick_commands[1]
    assert len(comparison_commands) == 1
    assert "--stop-after-epoch" not in comparison_commands[0]
    assert "--resume" in comparison_commands[0]


def test_full_run_completion_rejects_disabled_amp() -> None:
    pipeline = _module()
    spec = build_comparison_specs()[0]
    result = {"status": "completed", "amp_enabled": False, "resume_verified": False}
    provenance = {"source_commit": "a" * 40}

    with pytest.raises(RuntimeError, match="AMP"):
        pipeline.validate_run_completion(spec, result, provenance, "a" * 40)
