# WoundScope agent guidance

1. Read `PROJECT_PLAN.md` and `PROGRESS.md` before changing the repository. Treat locked decisions in the plan as an implementation contract.
2. Keep `.env`, FUSeg images/masks, image-level manifests, generated galleries, checkpoints, ONNX files, and other model artifacts out of Git.
3. Never print secret values. Use `.env.example` only for empty project-specific variable names.
4. Use `pathlib`, YAML configuration, and `WOUNDSCOPE_DATA_DIR` / `WOUNDSCOPE_ARTIFACT_DIR`; do not hard-code Windows, WSL, Colab, or Drive paths.
5. Do not claim patient-wise splitting, official-test metrics, clinical diagnosis, severity, prognosis, or treatment advice.
6. Do not invent experiment results. Update README result markers only from schema-valid completed full-run artifacts.
7. Run the current milestone gate, record exact PASS/FAIL evidence in `PROGRESS.md`, and only then mark the milestone complete.
8. Do not configure remotes, push, publish data/weights, or start full local GPU training without explicit user direction.
9. Use the repo-local `$woundscope-development` skill for continuation, milestone implementation, verification, and handoff work.
