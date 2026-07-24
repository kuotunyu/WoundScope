---
name: woundscope-development
description: Continue, implement, verify, or hand off the WoundScope medical image segmentation project. Use for WoundScope milestones, FUSeg data handling, training/evaluation/inference code, Colab workflows, Gradio/ONNX deployment, test gates, progress updates, or returning to this repository after an interruption.
---

# WoundScope Development

## Start safely

1. Read `PROJECT_PLAN.md` and `PROGRESS.md` completely.
2. Inspect Git status and the current milestone without reading `.env` values.
3. Treat locked decisions as binding. Discuss material changes before implementation.
4. Confirm `.env`, FUSeg data, image-level manifests, galleries, weights, and ONNX files remain ignored.

## Work the current milestone

1. Implement only the current milestone and prerequisites that unblock it.
2. Keep reusable logic in `src/woundscope`; keep `scripts/` and notebooks as thin entry points.
3. Use YAML config, `pathlib`, and documented environment variables for every path.
4. Use synthetic fixtures in CI. Never copy FUSeg images, labels, or image-bearing reports into tracked files.
5. Keep official validation out of tuning and official test out of quantitative claims.
6. Avoid full local GPU training unless the user explicitly requests it.
7. On Windows workspaces with CJK path segments, create `.venv` with a UTF-8-capable Python 3.11+; do not reuse the Anaconda 3.10 cp950 environment that fails on editable-install paths.
8. Treat data-report generation and training approval as separate gates. An integrity flag that permits writing a duplicate report never authorizes contaminated training; require an explicit recorded cross-split mitigation policy.

## Verify and report

1. Run the milestone gate from `PROJECT_PLAN.md` and preserve exact PASS/FAIL evidence.
2. Do not mark a milestone complete while a required check is missing or failing.
3. Do not write measured results unless backed by completed artifacts and provenance.
4. Update `PROGRESS.md` with changes, commands, artifacts, decisions, blockers, and the next action.
5. Create a local milestone-boundary commit only after the gate passes; never add a remote or push unless explicitly requested.

## Maintain project guidance

- Add a concise `AGENTS.md` rule only for behavior that must apply on every task.
- Update this skill only when a repeatable WoundScope workflow or pitfall becomes stable.
- Validate every skill revision with the skill-creator `quick_validate.py` command.
- Keep detailed scientific policy in `PROJECT_PLAN.md`; do not duplicate it here.
