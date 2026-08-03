"""CUDA-only, resumable stage-state execution for the Colab experiment pipeline."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import torch
import yaml

from woundscope.bundles import build_result_bundle
from woundscope.checkpointing import file_sha256
from woundscope.config import config_hash, load_config
from woundscope.dataset import read_manifest
from woundscope.orchestration import (
    MODEL_CONFIGS,
    STAGE_ORDER,
    PipelineState,
    RunSpec,
    build_comparison_specs,
    build_final_specs,
    build_quick_specs,
    select_losses,
    verify_seed42_reuse,
)
from woundscope.protocol import validate_exclude_train_contract
from woundscope.provenance import write_json_atomic
from woundscope.results import aggregate_official_validation


@dataclass(frozen=True)
class PipelinePaths:
    project_root: Path
    data_root: Path
    artifact_root: Path


@dataclass(frozen=True)
class StageContext:
    stage: str
    paths: PipelinePaths
    source_commit: str
    cuda_info: dict[str, Any]
    implementation_source_commit: str


@dataclass(frozen=True)
class StageOutcome:
    artifacts: list[Path]
    evidence: dict[str, Any]


StageHandler = Callable[[StageContext], StageOutcome]
CudaProbe = Callable[[], dict[str, Any]]


def probe_cuda() -> dict[str, Any]:
    if not torch.cuda.is_available():
        return {"available": False}
    properties = torch.cuda.get_device_properties(0)
    return {
        "available": True,
        "device_name": torch.cuda.get_device_name(0),
        "vram_gib": round(properties.total_memory / 2**30, 2),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
    }


def build_train_commands(spec: RunSpec, run_dir: str | Path) -> list[list[str]]:
    run_dir = Path(run_dir)
    base = [
        sys.executable,
        "scripts/train.py",
        "--model-config",
        spec.model_config,
        "--mode-config",
        f"configs/modes/{spec.mode}.yaml",
        "--device",
        "cuda",
        "--run-dir",
        str(run_dir),
        "--cross-split-policy",
        "exclude_train",
        "--set",
        f"training.loss={spec.loss}",
        "--set",
        f"project.seed={spec.seed}",
    ]
    completed_path = run_dir / "results.json"
    if completed_path.is_file():
        completed = json.loads(completed_path.read_text(encoding="utf-8"))
        if completed.get("status") == "completed":
            return []
    resumable = (run_dir / "trainer_state.pt").is_file() and (
        run_dir / "last_model.safetensors"
    ).is_file()
    if resumable:
        return [[*base, "--resume"]]
    if spec.mode == "quick":
        return [
            [*base, "--stop-after-epoch", "1"],
            [*base, "--resume"],
        ]
    return [[*base, "--resume"]]


def validate_run_completion(
    spec: RunSpec,
    result: dict[str, Any],
    provenance: dict[str, Any],
    source_commit: str,
) -> None:
    if result.get("status") != "completed":
        raise RuntimeError(f"Training did not complete: {spec.run_id}")
    if provenance.get("source_commit") != source_commit:
        raise RuntimeError(f"Training provenance source commit mismatch: {spec.run_id}")
    if result.get("amp_enabled") is not True:
        raise RuntimeError(f"CUDA AMP was not enabled: {spec.run_id}")
    if spec.mode == "quick" and result.get("resume_verified") is not True:
        raise RuntimeError(f"Quick run did not prove compatible resume: {spec.run_id}")


def _artifact_records(paths: PipelinePaths, artifacts: list[Path]) -> list[dict[str, Any]]:
    records = []
    artifact_root = paths.artifact_root.resolve()
    for artifact in artifacts:
        resolved = artifact.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(artifact_root):
            raise RuntimeError(f"Stage artifact is missing or outside artifact root: {artifact}")
        records.append(
            {
                "path": resolved.relative_to(artifact_root).as_posix(),
                "size": resolved.stat().st_size,
                "sha256": file_sha256(resolved),
            }
        )
    return records


def _artifact_validation_errors(paths: PipelinePaths, stage_record: dict[str, Any]) -> list[str]:
    records = stage_record.get("artifacts")
    if not isinstance(records, list) or not records:
        return ["artifact inventory is missing or empty"]
    errors: list[str] = []
    artifact_root = paths.artifact_root.resolve()
    for record in records:
        relative = str(record.get("path", ""))
        path = (artifact_root / relative).resolve()
        if not relative or not path.is_relative_to(artifact_root):
            errors.append(f"unsafe artifact path: {relative!r}")
        elif not path.is_file():
            errors.append(f"missing artifact: {relative}")
        elif path.stat().st_size != record.get("size"):
            errors.append(f"artifact size mismatch: {relative}")
        elif file_sha256(path) != record.get("sha256"):
            errors.append(f"artifact SHA-256 mismatch: {relative}")
    return errors


def _artifacts_valid(paths: PipelinePaths, stage_record: dict[str, Any]) -> bool:
    return not _artifact_validation_errors(paths, stage_record)


def run_pipeline(
    paths: PipelinePaths,
    *,
    source_commit: str,
    stage_handlers: Mapping[str, StageHandler],
    cuda_probe: CudaProbe = probe_cuda,
    implementation_source_commit: str | None = None,
) -> PipelineState:
    """Run all fixed stages, resuming only hash-valid completed stage outputs."""

    implementation_source_commit = implementation_source_commit or source_commit
    _validate_source_commit(source_commit, "source_commit")
    _validate_source_commit(implementation_source_commit, "implementation_source_commit")
    cuda_info = cuda_probe()
    if cuda_info.get("available") is not True:
        raise RuntimeError("CUDA is required for the Colab pipeline; CPU fallback is forbidden")
    if set(stage_handlers) != set(STAGE_ORDER):
        raise ValueError("Stage handlers must exactly match the locked pipeline stage set")

    paths.artifact_root.mkdir(parents=True, exist_ok=True)
    state_path = paths.artifact_root / "pipeline_state.json"
    state = PipelineState.load_or_create(state_path, source_commit)
    for stage in STAGE_ORDER:
        existing = state.stages.get(stage, {})
        if (
            existing.get("status") == "completed"
            and _artifacts_valid(paths, existing)
            # Colab data lives under volatile /content. Revalidate it on every
            # invocation before reusing any persisted downstream stage.
            and stage != "data_integrity"
        ):
            continue
        _execute_stage(
            state,
            state_path,
            stage,
            paths,
            source_commit,
            implementation_source_commit,
            cuda_info,
            stage_handlers[stage],
        )
    return state


def _validate_source_commit(value: str, label: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError(f"{label} must be a lowercase 40-character Git SHA")


def _execute_stage(
    state: PipelineState,
    state_path: Path,
    stage: str,
    paths: PipelinePaths,
    source_commit: str,
    implementation_source_commit: str,
    cuda_info: dict[str, Any],
    handler: StageHandler,
) -> None:
    state.record(
        state_path,
        stage,
        "running",
        cuda=cuda_info,
        implementation_source_commit=implementation_source_commit,
    )
    context = StageContext(
        stage,
        paths,
        source_commit,
        cuda_info,
        implementation_source_commit,
    )
    try:
        outcome = handler(context)
        records = _artifact_records(paths, outcome.artifacts)
    except Exception as exc:
        state.record(
            state_path,
            stage,
            "failed",
            error_type=type(exc).__name__,
            error=str(exc),
            implementation_source_commit=implementation_source_commit,
        )
        raise
    state.record(
        state_path,
        stage,
        "completed",
        artifacts=records,
        evidence=outcome.evidence,
        implementation_source_commit=implementation_source_commit,
    )


def resume_postprocessing(
    paths: PipelinePaths,
    *,
    source_commit: str,
    implementation_source_commit: str,
    stage_handlers: Mapping[str, StageHandler],
    cuda_probe: CudaProbe = probe_cuda,
) -> PipelineState:
    """Resume only data restoration, ONNX/benchmark, and safe handoff.

    Every completed training/evaluation artifact is hash-verified first. Any
    missing or changed upstream artifact aborts instead of falling back to
    training under a different implementation commit.
    """

    _validate_source_commit(source_commit, "source_commit")
    _validate_source_commit(implementation_source_commit, "implementation_source_commit")
    if set(stage_handlers) != set(STAGE_ORDER):
        raise ValueError("Stage handlers must exactly match the locked pipeline stage set")
    state_path = paths.artifact_root / "pipeline_state.json"
    state = PipelineState.load_or_create(state_path, source_commit)
    # Quick smoke artifacts and losing full-comparison ablations are not
    # dependencies of final ONNX export or the safe handoff. Requiring their
    # entire inventories made an irrelevant missing file force a recovery
    # refusal even when every selected final run remained intact.
    required_upstream_stages = (
        "locked_loss_selection",
        "multi_seed_final",
        "official_validation",
    )
    for stage in required_upstream_stages:
        record = state.stages.get(stage, {})
        validation_errors = _artifact_validation_errors(paths, record)
        if record.get("status") != "completed" or validation_errors:
            detail = "; ".join(validation_errors[:5]) or "stage status is not completed"
            raise RuntimeError(
                f"Postprocessing recovery refused: required stage {stage} is invalid: {detail}"
            )

    cuda_info = cuda_probe()
    if cuda_info.get("available") is not True:
        raise RuntimeError("CUDA is required for Colab postprocessing recovery")
    for stage in ("data_integrity", "onnx_and_benchmark", "safe_result_handoff"):
        record = state.stages.get(stage, {})
        if (
            stage != "data_integrity"
            and record.get("status") == "completed"
            and record.get("implementation_source_commit") == implementation_source_commit
            and _artifacts_valid(paths, record)
        ):
            continue
        _execute_stage(
            state,
            state_path,
            stage,
            paths,
            source_commit,
            implementation_source_commit,
            cuda_info,
            stage_handlers[stage],
        )
    return state


class _DefaultStageExecutor:
    def __init__(self, paths: PipelinePaths) -> None:
        self.paths = paths
        self.environment = os.environ.copy()
        self.environment["WOUNDSCOPE_DATA_DIR"] = str(paths.data_root)
        self.environment["WOUNDSCOPE_ARTIFACT_DIR"] = str(paths.artifact_root)

    def handlers(self) -> dict[str, StageHandler]:
        return {
            "data_integrity": self.data_integrity,
            "quick_gpu_gate": self.quick_gpu_gate,
            "full_comparison": self.full_comparison,
            "locked_loss_selection": self.locked_loss_selection,
            "multi_seed_final": self.multi_seed_final,
            "official_validation": self.official_validation,
            "onnx_and_benchmark": self.onnx_and_benchmark,
            "safe_result_handoff": self.safe_result_handoff,
        }

    def _run(self, command: list[str]) -> None:
        process = subprocess.Popen(
            command,
            cwd=self.paths.project_root,
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        output_tail: deque[str] = deque(maxlen=80)
        if process.stdout is None:
            raise RuntimeError("Unable to capture stage subprocess output")
        for line in process.stdout:
            print(line, end="", flush=True)
            output_tail.append(line.rstrip())
        return_code = process.wait()
        if return_code != 0:
            detail = "\n".join(output_tail) or "(subprocess produced no output)"
            raise RuntimeError(
                f"Stage command failed with exit code {return_code}: {command!r}\n"
                f"Last subprocess output:\n{detail}"
            )

    def _load_json(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _manifest_path(self) -> Path:
        return self.paths.data_root / "manifests" / "data_manifest.csv"

    def _summary_path(self) -> Path:
        return self.paths.data_root / "manifests" / "data_summary.json"

    def _challenge_dir(self) -> Path:
        config = load_config(self.paths.project_root / "configs/base.yaml")
        return (
            self.paths.data_root
            / str(config["data"]["raw_subdirectory"])
            / str(config["data"]["source_subdirectory"])
        )

    def _run_dir(self, spec: RunSpec) -> Path:
        return self.paths.artifact_root / "runs" / spec.run_id

    @staticmethod
    def _overrides(spec: RunSpec) -> list[str]:
        return ["--set", f"training.loss={spec.loss}", "--set", f"project.seed={spec.seed}"]

    @staticmethod
    def _require_finite(payload: Any, label: str) -> None:
        if isinstance(payload, float) and not torch.isfinite(torch.tensor(payload)):
            raise RuntimeError(f"Non-finite value in {label}")
        if isinstance(payload, dict):
            for key, value in payload.items():
                _DefaultStageExecutor._require_finite(value, f"{label}.{key}")
        elif isinstance(payload, list):
            for index, value in enumerate(payload):
                _DefaultStageExecutor._require_finite(value, f"{label}[{index}]")

    def _sample_input(self, selector: str) -> Path:
        row = next(
            row for row in read_manifest(self._manifest_path()) if row["internal_split"] == selector
        )
        return self._challenge_dir() / row["image_relpath"]

    def _training_files(self, run_dir: Path) -> list[Path]:
        required = [
            run_dir / "best_model.safetensors",
            run_dir / "last_model.safetensors",
            run_dir / "trainer_state.pt",
            run_dir / "history.csv",
            run_dir / "results.json",
            run_dir / "results.partial.json",
            run_dir / "config.resolved.yaml",
            run_dir / "provenance.json",
            run_dir / "cross_split_policy.json",
        ]
        events = sorted((run_dir / "tensorboard").glob("events.out.tfevents.*"))
        if not events:
            raise RuntimeError(f"TensorBoard event file is missing: {run_dir.name}")
        required.append(events[-1])
        missing = [path.name for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"Training artifacts are incomplete for {run_dir.name}: {missing}")
        return required

    def _evaluate_dev(self, spec: RunSpec, run_dir: Path) -> list[Path]:
        output = run_dir / "dev_evaluation"
        calibration = run_dir / "calibration.json"
        command = [
            sys.executable,
            "scripts/evaluate.py",
            "--model-config",
            spec.model_config,
            "--mode-config",
            f"configs/modes/{spec.mode}.yaml",
            "--checkpoint",
            str(run_dir / "best_model.safetensors"),
            "--calibration",
            str(calibration),
            "--selector",
            "dev",
            "--fit-calibration",
            "--output",
            str(output),
            "--device",
            "cuda",
            *self._overrides(spec),
        ]
        self._run(command)
        files = [
            calibration,
            output / "results.json",
            output / "per_image_metrics.csv",
            output / "metric_distributions.png",
        ]
        if not all(path.is_file() for path in files):
            raise RuntimeError(f"Dev calibration artifacts are incomplete for {run_dir.name}")
        self._require_finite(self._load_json(output / "results.json"), run_dir.name)
        return files

    def _export_benchmark_predict(
        self,
        spec: RunSpec,
        run_dir: Path,
        *,
        predict_sample: bool,
        gallery: bool,
    ) -> list[Path]:
        export_dir = run_dir / "exports"
        onnx_path = export_dir / "model.onnx"
        parity_path = export_dir / "onnx_parity.json"
        benchmark_path = export_dir / "benchmark.json"
        common_overrides = self._overrides(spec)
        self._run(
            [
                sys.executable,
                "scripts/export_onnx.py",
                "--model-config",
                spec.model_config,
                "--mode-config",
                f"configs/modes/{spec.mode}.yaml",
                "--checkpoint",
                str(run_dir / "best_model.safetensors"),
                "--calibration",
                str(run_dir / "calibration.json"),
                "--output",
                str(onnx_path),
                "--report",
                str(parity_path),
                *common_overrides,
            ]
        )
        self._run(
            [
                sys.executable,
                "scripts/benchmark.py",
                "--model",
                str(onnx_path),
                "--device",
                "cpu",
                "--output",
                str(benchmark_path),
            ]
        )
        files = [onnx_path, parity_path, benchmark_path]
        parity = self._load_json(parity_path)
        if parity.get("status") != "completed":
            raise RuntimeError(f"ONNX parity failed for {run_dir.name}")
        self._require_finite(parity, f"parity.{run_dir.name}")
        self._require_finite(self._load_json(benchmark_path), f"benchmark.{run_dir.name}")
        if predict_sample:
            prediction_dir = run_dir / "sample_predictions"
            sample = self._sample_input("dev")
            self._run(
                [
                    sys.executable,
                    "scripts/predict.py",
                    "--model",
                    str(onnx_path),
                    "--calibration",
                    str(run_dir / "calibration.json"),
                    "--input",
                    str(sample),
                    "--output",
                    str(prediction_dir),
                    "--device",
                    "cpu",
                ]
            )
            prediction_files = sorted(prediction_dir.glob("*"))
            if len([path for path in prediction_files if path.is_file()]) < 3:
                raise RuntimeError(f"Sample prediction artifacts are incomplete for {run_dir.name}")
            files.extend(path for path in prediction_files if path.is_file())
        if gallery:
            gallery_dir = run_dir / "error_gallery"
            self._run(
                [
                    sys.executable,
                    "scripts/generate_error_gallery.py",
                    "--model",
                    str(onnx_path),
                    "--calibration",
                    str(run_dir / "calibration.json"),
                    "--manifest",
                    str(self._manifest_path()),
                    "--challenge-dir",
                    str(self._challenge_dir()),
                    "--metrics",
                    str(run_dir / "official_validation" / "per_image_metrics.csv"),
                    "--output",
                    str(gallery_dir),
                    "--device",
                    "cpu",
                ]
            )
            gallery_files = sorted(gallery_dir.glob("*.png"))
            if len(gallery_files) != 5:
                raise RuntimeError(f"Locked five-category gallery is incomplete for {run_dir.name}")
            files.extend(gallery_files)
        return files

    def _train_and_calibrate(self, spec: RunSpec, *, quick_exports: bool) -> list[Path]:
        run_dir = self._run_dir(spec)
        for command in build_train_commands(spec, run_dir):
            self._run(command)
        files = self._training_files(run_dir)
        result = self._load_json(run_dir / "results.json")
        provenance = self._load_json(run_dir / "provenance.json")
        validate_run_completion(
            spec,
            result,
            provenance,
            str(self.environment.get("WOUNDSCOPE_SOURCE_COMMIT", "")),
        )
        self._require_finite(result, f"train.{run_dir.name}")
        files.extend(self._evaluate_dev(spec, run_dir))
        if quick_exports:
            files.extend(
                self._export_benchmark_predict(spec, run_dir, predict_sample=True, gallery=False)
            )
        return files

    def data_integrity(self, context: StageContext) -> StageOutcome:
        self._run(
            [
                sys.executable,
                "scripts/download_data.py",
                "--data-root",
                str(self.paths.data_root),
                "--allow-cross-split-exact",
            ]
        )
        summary = self._load_json(self._summary_path())
        rows = read_manifest(self._manifest_path())
        contract = validate_exclude_train_contract(
            summary,
            rows,
            expected_exclusion_count=7,
            expected_validation_count=200,
            split_seed=42,
        )
        if summary.get("counts") != {"train": 810, "validation": 200, "test": 200}:
            raise RuntimeError("Pinned official FUSeg counts do not match 810/200/200")
        if summary.get("masks") != {"train": 810, "validation": 200, "test": 0}:
            raise RuntimeError("Pinned official FUSeg mask counts do not match 810/200/0")
        protocol_dir = self.paths.artifact_root / "protocol"
        report_path = protocol_dir / "data_integrity.json"
        write_json_atomic(
            {
                "status": "completed",
                "source_commit": context.source_commit,
                "implementation_source_commit": context.implementation_source_commit,
                "data_revision": load_config(self.paths.project_root / "configs/base.yaml")["data"][
                    "source_revision"
                ],
                "counts": summary["counts"],
                "masks": summary["masks"],
                "structural_issue_count": len(summary.get("structural_issues", [])),
                "warning_count": len(summary.get("warnings", [])),
                "near_cross_split_count": len(summary.get("near_cross_split", [])),
                "policy": contract,
                "manifest_sha256": file_sha256(self._manifest_path()),
            },
            report_path,
        )
        exclusions = set(contract["excluded_training_samples"])
        sample = next(
            row
            for row in rows
            if row["internal_split"] == "train"
            and f"{row['split']}/{row['sample_id']}" not in exclusions
        )
        grid_path = self.paths.artifact_root / "private" / "augmentation_grid.png"
        self._run(
            [
                sys.executable,
                "scripts/inspect_augmentations.py",
                "--image",
                str(self._challenge_dir() / sample["image_relpath"]),
                "--mask",
                str(self._challenge_dir() / sample["mask_relpath"]),
                "--output",
                str(grid_path),
                "--device",
                "cpu",
            ]
        )
        return StageOutcome(
            artifacts=[report_path, grid_path],
            evidence={
                "counts": summary["counts"],
                "excluded_train_copies": 7,
                "retained_official_validation": 200,
                "augmentation_grid_private": True,
            },
        )

    def quick_gpu_gate(self, _context: StageContext) -> StageOutcome:
        artifacts: list[Path] = []
        run_summaries = []
        for spec in build_quick_specs():
            artifacts.extend(self._train_and_calibrate(spec, quick_exports=True))
            result = self._load_json(self._run_dir(spec) / "results.json")
            run_summaries.append(
                {
                    "run_id": spec.run_id,
                    "best_dev_dice": result["best_dev_dice"],
                    "epochs_completed": result["epochs_completed"],
                    "resume_verified": result["resume_verified"],
                    "amp_enabled": result["amp_enabled"],
                }
            )
        summary_path = self.paths.artifact_root / "quick" / "summary.json"
        write_json_atomic(
            {"status": "completed", "run_mode": "quick", "smoke_only": True, "runs": run_summaries},
            summary_path,
        )
        artifacts.append(summary_path)
        return StageOutcome(artifacts=artifacts, evidence={"completed_runs": 4, "smoke_only": True})

    def full_comparison(self, _context: StageContext) -> StageOutcome:
        artifacts: list[Path] = []
        for spec in build_comparison_specs():
            artifacts.extend(self._train_and_calibrate(spec, quick_exports=False))
        summary_path = self.paths.artifact_root / "comparison" / "summary.json"
        write_json_atomic(
            {
                "status": "completed",
                "run_mode": "full",
                "official_validation_used": False,
                "run_ids": [spec.run_id for spec in build_comparison_specs()],
            },
            summary_path,
        )
        artifacts.append(summary_path)
        return StageOutcome(artifacts=artifacts, evidence={"completed_runs": 4})

    def locked_loss_selection(self, context: StageContext) -> StageOutcome:
        candidates = []
        for spec in build_comparison_specs():
            report_path = self._run_dir(spec) / "dev_evaluation" / "results.json"
            report = self._load_json(report_path)
            candidates.append(
                {
                    "model": spec.model_name,
                    "loss": spec.loss,
                    "split": report["split"],
                    "source_commit": report["source_commit"],
                    "input_artifact_sha256": file_sha256(report_path),
                    "metrics": {
                        "mean_image_dice": report["image_summary"]["dice"]["mean"],
                        "global_dice": report["global_metrics"]["dice"],
                        "recall": report["global_metrics"]["recall"],
                    },
                }
            )
        selection = select_losses(candidates, context.source_commit)
        selection_path = self.paths.artifact_root / "selection" / "loss_selection.json"
        write_json_atomic(selection, selection_path)
        return StageOutcome(
            artifacts=[selection_path],
            evidence={
                "selected_losses": {
                    model: record["selected_loss"] for model, record in selection["models"].items()
                },
                "official_validation_used": False,
            },
        )

    def multi_seed_final(self, context: StageContext) -> StageOutcome:
        selection = self._load_json(self.paths.artifact_root / "selection" / "loss_selection.json")
        manifest_sha256 = file_sha256(self._manifest_path())
        config_hashes: dict[tuple[str, str, int], str] = {}
        for model, model_config in MODEL_CONFIGS.items():
            loss = str(selection["models"][model]["selected_loss"])
            for seed in (42, 43, 44):
                config = load_config(
                    self.paths.project_root / "configs/base.yaml",
                    self.paths.project_root / model_config,
                    self.paths.project_root / "configs/modes/full.yaml",
                    [f"training.loss={loss}", f"project.seed={seed}"],
                )
                config_hashes[(model, loss, seed)] = config_hash(config)
        final_specs = build_final_specs(
            selection,
            config_hashes=config_hashes,
            manifest_sha256=manifest_sha256,
        )
        artifacts: list[Path] = []
        index_runs = []
        for spec in final_specs:
            run_dir = self._run_dir(spec)
            reused = False
            if spec.seed == 42:
                comparison_spec = replace(spec, stage="comparison")
                comparison_dir = self._run_dir(comparison_spec)
                result = self._load_json(comparison_dir / "results.json")
                provenance = self._load_json(comparison_dir / "provenance.json")
                candidate = {
                    "status": result["status"],
                    "model": spec.model_name,
                    "loss": spec.loss,
                    "seed": spec.seed,
                    "config_sha256": result["config_hash"],
                    "manifest_sha256": result["manifest_hash"],
                    "checkpoint_sha256": result["best_checkpoint_sha256"],
                    "source_commit": provenance["source_commit"],
                }
                reuse = verify_seed42_reuse(candidate, spec)
                if reuse["reusable"] and candidate["source_commit"] == context.source_commit:
                    run_dir = comparison_dir
                    reused = True
                    artifacts.extend(self._training_files(run_dir))
                    artifacts.extend(
                        [
                            run_dir / "calibration.json",
                            run_dir / "dev_evaluation" / "results.json",
                        ]
                    )
            if not reused:
                artifacts.extend(self._train_and_calibrate(spec, quick_exports=False))
            index_runs.append(
                {
                    "model": spec.model_name,
                    "loss": spec.loss,
                    "seed": spec.seed,
                    "run_dir": run_dir.relative_to(self.paths.artifact_root).as_posix(),
                    "reused_comparison_seed42": reused,
                    "config_sha256": spec.config_sha256,
                    "manifest_sha256": spec.manifest_sha256,
                }
            )
        index_path = self.paths.artifact_root / "final" / "run_index.json"
        write_json_atomic(
            {
                "status": "completed",
                "source_commit": context.source_commit,
                "selection_sha256": file_sha256(
                    self.paths.artifact_root / "selection" / "loss_selection.json"
                ),
                "runs": index_runs,
            },
            index_path,
        )
        artifacts.append(index_path)
        return StageOutcome(
            artifacts=artifacts,
            evidence={
                "completed_runs": 6,
                "reused_seed42_runs": sum(run["reused_comparison_seed42"] for run in index_runs),
            },
        )

    def _final_index_specs(self) -> list[tuple[RunSpec, Path]]:
        index = self._load_json(self.paths.artifact_root / "final" / "run_index.json")
        return [
            (
                RunSpec(
                    stage="final",
                    mode="full",
                    model_name=str(run["model"]),
                    model_config=MODEL_CONFIGS[str(run["model"])],
                    loss=str(run["loss"]),
                    seed=int(run["seed"]),
                    config_sha256=str(run["config_sha256"]),
                    manifest_sha256=str(run["manifest_sha256"]),
                ),
                self.paths.artifact_root / str(run["run_dir"]),
            )
            for run in index["runs"]
        ]

    def official_validation(self, context: StageContext) -> StageOutcome:
        artifacts: list[Path] = []
        reports_by_model: dict[str, list[dict[str, Any]]] = {model: [] for model in MODEL_CONFIGS}
        for spec, run_dir in self._final_index_specs():
            output = run_dir / "official_validation"
            self._run(
                [
                    sys.executable,
                    "scripts/evaluate.py",
                    "--model-config",
                    spec.model_config,
                    "--mode-config",
                    "configs/modes/full.yaml",
                    "--checkpoint",
                    str(run_dir / "best_model.safetensors"),
                    "--calibration",
                    str(run_dir / "calibration.json"),
                    "--selector",
                    "official_validation",
                    "--output",
                    str(output),
                    "--device",
                    "cuda",
                    *self._overrides(spec),
                ]
            )
            files = [
                output / "results.json",
                output / "per_image_metrics.csv",
                output / "metric_distributions.png",
            ]
            if not all(path.is_file() for path in files):
                raise RuntimeError(f"Official validation artifacts are incomplete: {run_dir.name}")
            report = self._load_json(output / "results.json")
            if report.get("source_commit") != context.source_commit:
                raise RuntimeError("Official validation source commit mismatch")
            self._require_finite(report, f"official_validation.{run_dir.name}")
            reports_by_model[spec.model_name].append(report)
            artifacts.extend(files)
        experiments = [
            aggregate_official_validation(reports_by_model[model]) for model in MODEL_CONFIGS
        ]
        verified_path = self.paths.artifact_root / "aggregate" / "verified_results.json"
        write_json_atomic(
            {
                "status": "completed",
                "run_mode": "full",
                "verified": True,
                "split": "official_validation",
                "source_commit": context.source_commit,
                "experiments": experiments,
            },
            verified_path,
        )
        artifacts.append(verified_path)
        return StageOutcome(
            artifacts=artifacts,
            evidence={"models": 2, "seeds_per_model": 3, "bootstrap_samples": 2000},
        )

    def onnx_and_benchmark(self, context: StageContext) -> StageOutcome:
        artifacts: list[Path] = []
        runs = []
        for spec, run_dir in self._final_index_specs():
            files = self._export_benchmark_predict(
                spec, run_dir, predict_sample=False, gallery=True
            )
            artifacts.extend(files)
            runs.append(
                {
                    "model": spec.model_name,
                    "loss": spec.loss,
                    "seed": spec.seed,
                    "onnx_parity": "completed",
                    "benchmark": "completed",
                    "private_gallery_categories": [
                        "best",
                        "worst",
                        "small_area",
                        "low_light",
                        "background_interference",
                    ],
                }
            )
        summary_path = self.paths.artifact_root / "aggregate" / "onnx_benchmark.json"
        write_json_atomic(
            {
                "status": "completed",
                "source_commit": context.source_commit,
                "implementation_source_commit": context.implementation_source_commit,
                "runs": runs,
            },
            summary_path,
        )
        artifacts.append(summary_path)
        return StageOutcome(artifacts=artifacts, evidence={"completed_runs": 6})

    @staticmethod
    def _copy_json_safely(source: Path, destination: Path, *, omit: set[str] | None = None) -> None:
        payload = json.loads(source.read_text(encoding="utf-8"))
        for key in omit or set():
            payload.pop(key, None)
        write_json_atomic(payload, destination)

    def safe_result_handoff(self, context: StageContext) -> StageOutcome:
        handoff_dir = self.paths.artifact_root / "handoff"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        output = handoff_dir / f"woundscope_colab_results_{context.source_commit[:12]}.zip"
        with tempfile.TemporaryDirectory(prefix="safe-staging-", dir=handoff_dir) as temporary:
            staging = Path(temporary)
            self._copy_json_safely(
                self.paths.artifact_root / "aggregate" / "verified_results.json",
                staging / "aggregate" / "verified_results.json",
            )
            self._copy_json_safely(
                self.paths.artifact_root / "selection" / "loss_selection.json",
                staging / "selection" / "loss_selection.json",
            )
            self._copy_json_safely(
                self.paths.artifact_root / "aggregate" / "onnx_benchmark.json",
                staging / "aggregate" / "onnx_benchmark.json",
            )
            write_json_atomic(
                {
                    "source_commit": context.source_commit,
                    "implementation_source_commit": context.implementation_source_commit,
                    "cuda": context.cuda_info,
                    "cross_split_policy": "exclude_train",
                    "excluded_train_copies": 7,
                    "retained_official_validation": 200,
                },
                staging / "environment" / "colab_environment.json",
            )
            for spec, run_dir in self._final_index_specs():
                stem = f"{spec.model_name}_{spec.loss}_seed{spec.seed}"
                self._copy_json_safely(
                    run_dir / "official_validation" / "results.json",
                    staging / "per_seed" / f"{stem}.json",
                    omit={"confusions"},
                )
                self._copy_json_safely(
                    run_dir / "calibration.json",
                    staging / "calibration" / f"{stem}.json",
                )
                provenance = self._load_json(run_dir / "provenance.json")
                cross_policy = provenance.get("cross_split_policy", {})
                safe_provenance = {
                    key: provenance.get(key)
                    for key in (
                        "source_commit",
                        "data_revision",
                        "manifest_sha256",
                        "config_sha256",
                        "seed",
                        "packages",
                        "cuda_available",
                        "cuda_version",
                        "cudnn_version",
                        "best_checkpoint_sha256",
                        "last_checkpoint_sha256",
                    )
                }
                safe_provenance["cross_split_policy"] = {
                    "policy": cross_policy.get("policy"),
                    "finding_count": cross_policy.get("finding_count"),
                    "excluded_training_count": len(
                        cross_policy.get("excluded_training_samples", [])
                    ),
                }
                write_json_atomic(safe_provenance, staging / "provenance" / f"{stem}.json")
                config = yaml.safe_load(
                    (run_dir / "config.resolved.yaml").read_text(encoding="utf-8")
                )
                config["data"]["root"] = "${WOUNDSCOPE_DATA_DIR}"
                config["artifacts"]["root"] = "${WOUNDSCOPE_ARTIFACT_DIR}"
                config_path = staging / "configs" / f"{stem}.yaml"
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(
                    yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
                )
                history_path = staging / "histories" / f"{stem}.csv"
                history_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(run_dir / "history.csv", history_path)
                self._copy_json_safely(
                    run_dir / "exports" / "onnx_parity.json",
                    staging / "onnx_parity" / f"{stem}.json",
                )
                self._copy_json_safely(
                    run_dir / "exports" / "benchmark.json",
                    staging / "benchmarks" / f"{stem}.json",
                )
                chart_path = staging / "public_charts" / f"{stem}_metric_distributions.png"
                chart_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(
                    run_dir / "official_validation" / "metric_distributions.png", chart_path
                )
            build_result_bundle(staging, output, source_commit=context.source_commit)
        return StageOutcome(
            artifacts=[output],
            evidence={
                "safe_bundle": output.name,
                "weights_included": False,
                "source_images_included": False,
            },
        )


def create_default_stage_handlers(paths: PipelinePaths) -> dict[str, StageHandler]:
    """Create the production handlers used by the thin Colab entry point."""

    return _DefaultStageExecutor(paths).handlers()
