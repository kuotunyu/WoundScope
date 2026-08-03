"""Resume only WoundScope data restoration, ONNX/benchmark, and safe handoff."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from woundscope.colab_pipeline import PipelinePaths, resume_postprocessing


def _manifest_source_commit(project_root: Path) -> str:
    manifest_path = project_root / "bundle_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing extracted source bundle manifest: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid extracted source bundle manifest: {manifest_path}") from exc
    if manifest.get("kind") != "source" or manifest.get("schema_version") != 1:
        raise SystemExit("Extracted source bundle manifest kind or schema is incompatible")
    return str(manifest.get("source_commit", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True, help="Original training source commit")
    parser.add_argument("--implementation-source-commit", required=True)
    args = parser.parse_args()

    from woundscope.colab_pipeline import create_default_stage_handlers

    project_root = args.project_root.resolve()
    manifest_source_commit = _manifest_source_commit(project_root)
    if manifest_source_commit != args.implementation_source_commit:
        raise SystemExit(
            "implementation source commit does not match the extracted source bundle manifest"
        )
    paths = PipelinePaths(
        project_root=project_root,
        data_root=args.data_dir.resolve(),
        artifact_root=args.artifact_dir.resolve(),
    )
    os.environ["WOUNDSCOPE_DATA_DIR"] = str(paths.data_root)
    os.environ["WOUNDSCOPE_ARTIFACT_DIR"] = str(paths.artifact_root)
    os.environ["WOUNDSCOPE_SOURCE_COMMIT"] = args.source_commit
    os.environ["WOUNDSCOPE_IMPLEMENTATION_SOURCE_COMMIT"] = args.implementation_source_commit
    state = resume_postprocessing(
        paths,
        source_commit=args.source_commit,
        implementation_source_commit=args.implementation_source_commit,
        stage_handlers=create_default_stage_handlers(paths),
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "source_commit": args.source_commit,
                "implementation_source_commit": args.implementation_source_commit,
                "stages": state.stages,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
