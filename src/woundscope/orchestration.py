"""Deterministic experiment matrices, selection, reuse, and stage-state contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from woundscope.provenance import write_json_atomic

MODEL_CONFIGS = {
    "unet_efficientnet_b0": "configs/models/unet_efficientnet_b0.yaml",
    "segformer_b0": "configs/models/segformer_b0.yaml",
}
LOSSES = ("bce_dice", "focal_tversky")
FINAL_SEEDS = (42, 43, 44)
STAGE_ORDER = (
    "data_integrity",
    "quick_gpu_gate",
    "full_comparison",
    "locked_loss_selection",
    "multi_seed_final",
    "official_validation",
    "onnx_and_benchmark",
    "safe_result_handoff",
)


@dataclass(frozen=True)
class RunSpec:
    stage: str
    mode: str
    model_name: str
    model_config: str
    loss: str
    seed: int
    config_sha256: str | None = None
    manifest_sha256: str | None = None

    @property
    def run_id(self) -> str:
        return f"{self.stage}_{self.model_name}_{self.loss}_seed{self.seed}"


@dataclass
class PipelineState:
    source_commit: str
    stages: dict[str, dict[str, Any]]

    @classmethod
    def load_or_create(cls, path: str | Path, source_commit: str) -> PipelineState:
        path = Path(path)
        if not path.is_file():
            return cls(source_commit=source_commit, stages={})
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("source_commit") != source_commit:
            raise ValueError("Pipeline state source commit is incompatible with this bundle")
        return cls(source_commit=source_commit, stages=dict(payload.get("stages", {})))

    def record(self, path: str | Path, stage: str, status: str, **evidence: Any) -> None:
        if stage not in STAGE_ORDER:
            raise ValueError(f"Unknown pipeline stage: {stage}")
        if status not in {"running", "completed", "failed"}:
            raise ValueError(f"Unknown pipeline stage status: {status}")
        self.stages[stage] = {"status": status, **evidence}
        write_json_atomic(asdict(self), path)


def _build_specs(stage: str, mode: str) -> list[RunSpec]:
    return [
        RunSpec(
            stage=stage,
            mode=mode,
            model_name=model_name,
            model_config=model_config,
            loss=loss,
            seed=42,
        )
        for model_name, model_config in MODEL_CONFIGS.items()
        for loss in LOSSES
    ]


def build_quick_specs() -> list[RunSpec]:
    return _build_specs("quick", "quick")


def build_comparison_specs() -> list[RunSpec]:
    return _build_specs("comparison", "full")


def build_final_specs(
    selection: dict[str, Any],
    *,
    config_hashes: dict[tuple[str, str, int], str] | None = None,
    manifest_sha256: str | None = None,
) -> list[RunSpec]:
    config_hashes = config_hashes or {}
    return [
        RunSpec(
            stage="final",
            mode="full",
            model_name=model_name,
            model_config=MODEL_CONFIGS[model_name],
            loss=str(selection["models"][model_name]["selected_loss"]),
            seed=seed,
            config_sha256=config_hashes.get(
                (model_name, str(selection["models"][model_name]["selected_loss"]), seed)
            ),
            manifest_sha256=manifest_sha256,
        )
        for model_name in MODEL_CONFIGS
        for seed in FINAL_SEEDS
    ]


def _require_sha(value: object, length: int, label: str) -> str:
    normalized = str(value)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", normalized) is None:
        raise ValueError(f"{label} must be a lowercase {length}-character hexadecimal hash")
    return normalized


def select_losses(candidates: list[dict[str, Any]], source_commit: str) -> dict[str, Any]:
    """Select one loss per model from internal-dev aggregate evidence only."""

    _require_sha(source_commit, 40, "source_commit")
    if any(candidate.get("split") != "dev" for candidate in candidates):
        raise ValueError("Loss selection may use internal dev only")
    if len(candidates) != len(MODEL_CONFIGS) * len(LOSSES):
        raise ValueError("Loss selection requires all four model/loss candidates")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        if candidate.get("source_commit") != source_commit:
            raise ValueError("Candidate source commit does not match selection source commit")
        model = str(candidate.get("model"))
        loss = str(candidate.get("loss"))
        if model not in MODEL_CONFIGS or loss not in LOSSES or (model, loss) in seen:
            raise ValueError(f"Unexpected or duplicate loss-selection candidate: {model}/{loss}")
        metrics = candidate.get("metrics", {})
        selected_metrics = {
            name: float(metrics[name]) for name in ("mean_image_dice", "global_dice", "recall")
        }
        if not all(math.isfinite(value) for value in selected_metrics.values()):
            raise ValueError(f"Non-finite loss-selection metric for {model}/{loss}")
        normalized.append(
            {
                "model": model,
                "loss": loss,
                "split": "dev",
                "metrics": selected_metrics,
                "input_artifact_sha256": _require_sha(
                    candidate.get("input_artifact_sha256"), 64, "input_artifact_sha256"
                ),
            }
        )
        seen.add((model, loss))

    models: dict[str, Any] = {}
    for model in MODEL_CONFIGS:
        model_candidates = [candidate for candidate in normalized if candidate["model"] == model]
        winner = max(
            model_candidates,
            key=lambda candidate: (
                candidate["metrics"]["mean_image_dice"],
                candidate["metrics"]["global_dice"],
                candidate["metrics"]["recall"],
                candidate["loss"] == "bce_dice",
            ),
        )
        models[model] = {
            "selected_loss": winner["loss"],
            "selected_input_artifact_sha256": winner["input_artifact_sha256"],
        }

    combined_digest = hashlib.sha256(
        "".join(sorted(candidate["input_artifact_sha256"] for candidate in normalized)).encode()
    ).hexdigest()
    return {
        "status": "completed",
        "source_commit": source_commit,
        "official_validation_used": False,
        "selection_order": [
            "mean_image_dice",
            "global_dice",
            "recall",
            "prefer_bce_dice",
        ],
        "candidates": sorted(normalized, key=lambda item: (item["model"], item["loss"])),
        "input_artifacts_sha256": combined_digest,
        "models": models,
    }


def verify_seed42_reuse(candidate: dict[str, Any], final_spec: RunSpec) -> dict[str, Any]:
    """Return explicit mismatch evidence for a possible comparison-run reuse."""

    expected = {
        "status": "completed",
        "model": final_spec.model_name,
        "loss": final_spec.loss,
        "seed": 42,
        "config_sha256": final_spec.config_sha256,
        "manifest_sha256": final_spec.manifest_sha256,
    }
    mismatches = sorted(key for key, value in expected.items() if candidate.get(key) != value)
    checkpoint = str(candidate.get("checkpoint_sha256", ""))
    if re.fullmatch(r"[0-9a-f]{64}", checkpoint) is None:
        mismatches.append("checkpoint_sha256")
    if final_spec.seed != 42:
        mismatches.append("final_seed")
    return {
        "reusable": not mismatches,
        "mismatches": sorted(set(mismatches)),
        "checkpoint_sha256": checkpoint if not mismatches else None,
        "source_commit": candidate.get("source_commit"),
    }
