from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from woundscope.orchestration import STAGE_ORDER, build_comparison_specs, build_quick_specs


def _module():
    return importlib.import_module("woundscope.colab_pipeline")


def test_pipeline_runs_stages_in_order_revalidates_data_and_skips_other_completed_stages(
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
        if context.stage == "data_integrity":
            manifest_dir = paths.data_root / "manifests"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            (manifest_dir / "data_manifest.csv").write_text("sample_id\n", encoding="utf-8")
            (manifest_dir / "data_summary.json").write_text("{}", encoding="utf-8")
            (paths.data_root / "raw" / "fuseg").mkdir(parents=True, exist_ok=True)
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
    assert calls == ["data_integrity"]
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


def test_pipeline_revalidates_volatile_data_on_every_invocation(tmp_path: Path) -> None:
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
        if context.stage == "data_integrity":
            manifest_dir = paths.data_root / "manifests"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            (manifest_dir / "data_manifest.csv").write_text("sample_id\n", encoding="utf-8")
            (manifest_dir / "data_summary.json").write_text("{}", encoding="utf-8")
            challenge_dir = paths.data_root / "raw" / "fuseg" / "challenge"
            challenge_dir.mkdir(parents=True, exist_ok=True)
        return pipeline.StageOutcome(artifacts=[marker], evidence={"stage": context.stage})

    handlers = {stage: handler for stage in STAGE_ORDER}
    pipeline.run_pipeline(
        paths,
        source_commit="a" * 40,
        stage_handlers=handlers,
        cuda_probe=lambda: {"available": True},
    )
    calls.clear()

    pipeline.run_pipeline(
        paths,
        source_commit="a" * 40,
        stage_handlers=handlers,
        cuda_probe=lambda: {"available": True},
    )

    assert calls == ["data_integrity"]


def test_stage_command_failure_preserves_subprocess_output(tmp_path: Path) -> None:
    pipeline = _module()
    paths = pipeline.PipelinePaths(tmp_path, tmp_path / "data", tmp_path / "artifacts")
    executor = pipeline._DefaultStageExecutor(paths)
    command = [
        sys.executable,
        "-c",
        "import sys; print('diagnostic stdout'); print('diagnostic stderr', file=sys.stderr); "
        "raise SystemExit(7)",
    ]

    with pytest.raises(RuntimeError) as error:
        executor._run(command)

    message = str(error.value)
    assert "exit code 7" in message
    assert "diagnostic stdout" in message
    assert "diagnostic stderr" in message


def test_postprocessing_resume_reuses_completed_training_without_calling_training_handlers(
    tmp_path: Path,
) -> None:
    pipeline = _module()
    paths = pipeline.PipelinePaths(
        project_root=tmp_path / "project",
        data_root=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
    )
    paths.project_root.mkdir()
    first_calls: list[str] = []

    def first_handler(context):
        first_calls.append(context.stage)
        if context.stage == "onnx_and_benchmark":
            raise RuntimeError("synthetic ONNX parity failure")
        marker = paths.artifact_root / "stage_markers" / f"{context.stage}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f'{{"stage": "{context.stage}"}}', encoding="utf-8")
        return pipeline.StageOutcome(artifacts=[marker], evidence={"stage": context.stage})

    with pytest.raises(RuntimeError, match="ONNX parity"):
        pipeline.run_pipeline(
            paths,
            source_commit="a" * 40,
            stage_handlers={stage: first_handler for stage in STAGE_ORDER},
            cuda_probe=lambda: {"available": True},
        )
    assert first_calls == list(STAGE_ORDER[:7])

    resume_calls: list[str] = []

    def resume_handler(context):
        resume_calls.append(context.stage)
        assert context.implementation_source_commit == "b" * 40
        if context.stage not in {"data_integrity", "onnx_and_benchmark", "safe_result_handoff"}:
            raise AssertionError("training handler must not run during postprocessing recovery")
        marker = paths.artifact_root / "repair_markers" / f"{context.stage}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f'{{"stage": "{context.stage}"}}', encoding="utf-8")
        return pipeline.StageOutcome(artifacts=[marker], evidence={"stage": context.stage})

    resumed = pipeline.resume_postprocessing(
        paths,
        source_commit="a" * 40,
        implementation_source_commit="b" * 40,
        stage_handlers={stage: resume_handler for stage in STAGE_ORDER},
        cuda_probe=lambda: {"available": True},
    )

    assert resume_calls == ["data_integrity", "onnx_and_benchmark", "safe_result_handoff"]
    for stage in resume_calls:
        assert resumed.stages[stage]["implementation_source_commit"] == "b" * 40


def test_postprocessing_resume_aborts_when_upstream_training_artifact_is_invalid(
    tmp_path: Path,
) -> None:
    pipeline = _module()
    paths = pipeline.PipelinePaths(tmp_path / "project", tmp_path / "data", tmp_path / "artifacts")
    paths.project_root.mkdir()
    state_path = paths.artifact_root / "pipeline_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        '{"source_commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","stages":{}}',
        encoding="utf-8",
    )
    called = False

    def handler(_context):
        nonlocal called
        called = True
        raise AssertionError("no stage should execute")

    with pytest.raises(RuntimeError, match="quick_gpu_gate"):
        pipeline.resume_postprocessing(
            paths,
            source_commit="a" * 40,
            implementation_source_commit="b" * 40,
            stage_handlers={stage: handler for stage in STAGE_ORDER},
            cuda_probe=lambda: {"available": True},
        )
    assert called is False
