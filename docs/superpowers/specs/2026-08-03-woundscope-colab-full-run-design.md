# WoundScope Colab Full-Run Design

## Status and authority

This design implements the user-approved 2026-08-03 full-run contract together with the
locked decisions in `PROJECT_PLAN.md`. The approved cross-split policy is `exclude_train`:
exclude only the seven exact official-train copies, retain all 200 official-validation
samples, keep pHash findings as warnings, and never report official-test metrics.

## Considered approaches

1. Extend the notebook with more mode switches. This minimizes new files but keeps manual
   quick/comparison/final transitions and makes resume, selection, and handoff hard to test.
2. Add a small Python stage orchestrator and keep the notebook as a thin launcher. This is
   the selected approach because stages, compatibility gates, artifact checks, and safe ZIP
   construction become deterministic and unit-testable without adding a workflow dependency.
3. Add a general workflow engine. This would provide scheduling features but adds a new
   dependency and operational surface that the fixed eight-stage pipeline does not need.

## Architecture

`src/woundscope/orchestration.py` owns the stage graph, run matrix, immutable run identities,
resume rules, deterministic loss selection, seed-42 reuse checks, and stage-state records.
`scripts/run_colab_pipeline.py` is a thin CLI adapter that supplies project/data/artifact paths
and executes all eight stages in order on CUDA. The notebook mounts Drive, extracts the source
bundle safely, installs dependencies, verifies CUDA, and invokes that single command.

Training keeps using `scripts/train.py` and `src/woundscope/training.py`. Quick runs use the
same two-epoch config for both invocations: the first invocation deliberately stops after the
first persisted epoch, and the second resumes from the compatible trainer state. This proves
resume behavior rather than merely checking that resume code exists. Full comparison uses
seed 42 for all four model/loss candidates. Selection consumes internal-dev aggregate metrics
only and applies mean image Dice, global Dice, recall, then BCE+Dice as the exact tie order.

After selection is written and hashed, final runs use seeds 42/43/44 per model. A comparison
seed-42 run is reused only when config hash, manifest hash, model/loss/seed, checkpoint hash,
and completed status all match. Official validation starts only after all selected checkpoints
and calibration artifacts are frozen.

## Data and artifact flow

The integrity stage validates the pinned revision, 810/200/200 counts, pairing/corruption,
seven exact cross-split findings, `exclude_train` exclusions, retained validation count, and
duplicate-group-isolated seed-42 internal split. Augmentation grids, sample predictions,
per-image metrics, checkpoints, ONNX, TensorBoard, manifests, and raw data remain private in
the Drive artifact root.

The final safe handoff ZIP contains only aggregate/per-seed result JSON, the selection record,
resolved configs, provenance, histories, calibration metadata, environment data, ONNX parity,
benchmarks, aggregate plots, and a SHA-256 inventory. It rejects absolute paths and sensitive
file classes. It excludes raw data, manifests, per-image tables, images derived from source
samples, checkpoints, weights, ONNX models, TensorBoard events, secrets, and Drive paths.

The source ZIP is built from a clean committed snapshot using an explicit allowlist. It excludes
`.git`, `.env`, data, artifacts, generated reports, local plans/notes, caches, and absolute paths.
Its manifest records the source commit, file sizes, and SHA-256 hashes. A clean extraction must
pass imports, tests, and notebook preflight before upload.

## Failure and resume behavior

Every stage writes an atomic machine-readable state record. A completed stage is skipped only
after its declared outputs and hashes validate; failed or incomplete stages retain their status
and are resumed. Existing completed run directories are never overwritten. A compatibility
mismatch stops the pipeline with a precise error instead of starting a second run under the
same identity. Quick CUDA absence is fatal and never falls back to CPU.

## Verification

Tests cover protocol exclusion, unchanged validation, group isolation, stage ordering, quick
matrix and forced resume, finite metrics, selection ties, reuse compatibility, frozen-validation
ordering, source ZIP allowlisting/path safety, handoff privacy/checksums/schema, result aggregate
recomputation, and notebook thin-wrapper structure. The local gate is Ruff, format check, Mypy
only if configured, all CPU tests, notebook tests, a synthetic CPU vertical slice, official data
integration, ignore/privacy audit, and clean committed source extraction. Colab supplies the CUDA,
AMP, full-training, ONNX/parity, benchmark, and official-validation evidence.

