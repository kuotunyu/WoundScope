"""Run the complete CUDA-only WoundScope staged experiment and safe handoff."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from woundscope.colab_pipeline import PipelinePaths, run_pipeline


def _environment_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} must be set or supplied by a CLI path option")
    return Path(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    from woundscope.colab_pipeline import create_default_stage_handlers

    paths = PipelinePaths(
        project_root=args.project_root.resolve(),
        data_root=(args.data_dir or _environment_path("WOUNDSCOPE_DATA_DIR")).resolve(),
        artifact_root=(args.artifact_dir or _environment_path("WOUNDSCOPE_ARTIFACT_DIR")).resolve(),
    )
    os.environ["WOUNDSCOPE_DATA_DIR"] = str(paths.data_root)
    os.environ["WOUNDSCOPE_ARTIFACT_DIR"] = str(paths.artifact_root)
    os.environ["WOUNDSCOPE_SOURCE_COMMIT"] = args.source_commit
    state = run_pipeline(
        paths,
        source_commit=args.source_commit,
        stage_handlers=create_default_stage_handlers(paths),
    )
    print(json.dumps({"status": "completed", "stages": state.stages}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
