# WoundScope Colab Full-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute one resumable Colab pipeline from integrity audit through a privacy-safe verified results handoff and release-candidate update.

**Architecture:** A focused Python orchestrator owns the fixed stage graph and delegates existing training/evaluation/export commands through an injectable command runner. Separate source-bundle and result-handoff modules enforce immutable provenance, allowlists, path safety, checksums, and public/private artifact boundaries; the Colab notebook remains a thin single-launch wrapper.

**Tech Stack:** Python 3.10–3.12, PyTorch 2.x, CUDA AMP, safetensors, ONNX Runtime, YAML, JSON/CSV, zipfile, pytest, Ruff, Google Colab and Google Drive.

## Global Constraints

- Use only EfficientNet-B0 U-Net and SegFormer-B0 with BCE+Dice and Focal+Tversky.
- Use `CROSS_SPLIT_POLICY="exclude_train"`; exclude only the seven official-train copies and retain official validation intact.
- Quick is seed 42, 128 train, 32 internal-dev, two epochs, and must require CUDA.
- Full comparison is the four model/loss candidates at seed 42; selection order is mean image Dice, global Dice, recall, then BCE+Dice.
- Final selected runs use seeds 42, 43, and 44; reuse seed 42 only after hash/provenance compatibility.
- Official validation cannot affect checkpoint, loss, threshold, temperature, or any other tuning.
- Official test has no quantitative metrics; never claim patient-wise generalization or clinical capability.
- Never track or place in the safe handoff raw data, image-level manifests, source-derived images, galleries, checkpoints, weights, ONNX, TensorBoard, secrets, authentication material, or absolute Drive paths.
- Do not use the local RTX 4090, configure a remote, push, tag, publish, or call a paid API.

---

### Task 1: Lock the duplicate mitigation contract

**Files:**
- Modify: `PROJECT_PLAN.md`
- Modify: `PROGRESS.md`
- Modify: `README.md`
- Modify: `DATA_CARD.md`
- Modify: `MODEL_CARD.md`
- Modify: `src/woundscope/protocol.py`
- Test: `tests/test_protocol_reporting.py`

**Interfaces:**
- Consumes: existing `resolve_cross_split_policy(summary, policy)`.
- Produces: `validate_exclude_train_contract(summary, manifest_rows) -> dict[str, Any]` and a locked policy record with exclusion and retained-validation counts.

- [ ] **Step 1: Write failing protocol regressions**

```python
def test_exclude_train_removes_only_train_copies_and_retains_validation():
    rows = [
        {"split": "train", "sample_id": "t", "internal_split": "train"},
        {"split": "validation", "sample_id": "v", "internal_split": "official_validation"},
    ]
    summary = {"counts": {"validation": 1}, "exact_cross_split": [
        {"splits": ["train", "validation"], "samples": ["train/t", "validation/v"]}
    ]}
    record = validate_exclude_train_contract(summary, rows)
    assert record["excluded_training_samples"] == ["train/t"]
    assert record["retained_official_validation"] == 1
```

- [ ] **Step 2: Run the focused test and confirm it fails before implementation**

Run: `.venv\Scripts\python.exe -m pytest tests/test_protocol_reporting.py -q`
Expected: FAIL because `validate_exclude_train_contract` is not defined.

- [ ] **Step 3: Implement exact contract validation and lock the documentation decision**

Implement checks for split-qualified duplicate keys, train-only exclusions, validation count
retention, policy `exclude_train`, and split seed 42/group isolation evidence. Replace the open
Decision Log row and stale blocker text with the approved locked decision.

- [ ] **Step 4: Run focused protocol and data-integrity tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_protocol_reporting.py tests/test_data_integrity.py -q`
Expected: PASS with no validation sample removed.

- [ ] **Step 5: Commit the protocol boundary**

Run: `git commit -m "fix(protocol): exclude exact train copies from locked validation"`

### Task 2: Make quick resume and run artifacts explicit

**Files:**
- Modify: `src/woundscope/training.py`
- Modify: `scripts/train.py`
- Modify: `src/woundscope/provenance.py`
- Test: `tests/test_training_vertical.py`
- Test: `tests/test_checkpointing.py`

**Interfaces:**
- Consumes: `train_model(..., resume: bool)` and atomic checkpoint helpers.
- Produces: `train_model(..., stop_after_epoch: int | None = None)` with `resume_verified`, `amp_enabled`, finite-metric validation, `config.resolved.yaml`, and `WOUNDSCOPE_SOURCE_COMMIT` provenance fallback.

- [ ] **Step 1: Write failing forced-interruption/resume tests**

```python
first = train_model(model, loader, loader, config, run_dir,
                    manifest_hash="m", stop_after_epoch=1)
assert first["status"] == "interrupted_for_resume_test"
second = train_model(TinyUNet(base_channels=2), loader, loader, config, run_dir,
                     manifest_hash="m", resume=True)
assert second["resume_verified"] is True
assert second["epochs_completed"] == 2
```

- [ ] **Step 2: Run the focused vertical-slice test and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_training_vertical.py -q`
Expected: FAIL because `stop_after_epoch` and resume evidence are absent.

- [ ] **Step 3: Implement the minimal interruption/resume contract**

Keep the resolved config hash unchanged between invocations, return partial status only when work
remains, reject non-finite epoch metrics, record AMP state, write `config.resolved.yaml`, and never
overwrite a completed compatible run.

- [ ] **Step 4: Run vertical slice and checkpoint gates**

Run: `.venv\Scripts\python.exe -m pytest tests/test_training_vertical.py tests/test_checkpointing.py -q`
Expected: PASS including an actual resumed epoch.

### Task 3: Implement deterministic stage planning and loss selection

**Files:**
- Create: `src/woundscope/orchestration.py`
- Test: `tests/test_orchestration.py`

**Interfaces:**
- Produces: `StageName`, `RunSpec`, `build_quick_specs()`, `build_comparison_specs()`, `select_losses(candidate_reports, source_commit)`, `verify_seed42_reuse(candidate, final_spec)`, and atomic `PipelineState` records.

- [ ] **Step 1: Write failing matrix, tie-order, and reuse tests**

```python
assert len(build_quick_specs()) == 4
selection = select_losses(candidate_reports, "a" * 40)
assert selection["models"]["unet_efficientnet_b0"]["selected_loss"] == "bce_dice"
assert selection["official_validation_used"] is False
assert verify_seed42_reuse(candidate, final_spec)["reusable"] is True
```

- [ ] **Step 2: Run orchestration tests and confirm import failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_orchestration.py -q`
Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement fixed matrices, lexicographic selection, hashes, and state records**

Use exact model/loss/seed values, compare descending mean image Dice/global Dice/recall with
`bce_dice` as the final deterministic preference, hash every candidate input, and represent
failed/incomplete/completed stages without deleting negative runs.

- [ ] **Step 4: Run orchestration tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_orchestration.py -q`
Expected: PASS.

### Task 4: Implement the CUDA-only eight-stage runner

**Files:**
- Create: `scripts/run_colab_pipeline.py`
- Modify: `scripts/export_onnx.py`
- Modify: `scripts/benchmark.py`
- Modify: `scripts/predict.py`
- Test: `tests/test_colab_pipeline.py`

**Interfaces:**
- Consumes: orchestration run specs, existing train/evaluate/export/predict commands, and environment-provided data/artifact roots.
- Produces: `run_pipeline(project_root, data_root, artifact_root, source_commit, runner)` and machine-readable stage/run summaries.

- [ ] **Step 1: Write failing runner tests with an injected fake command runner**

```python
state = run_pipeline(paths, source_commit="a" * 40, runner=fake_runner)
assert state.completed_stages == EXPECTED_STAGE_ORDER
assert fake_runner.cuda_required is True
assert fake_runner.quick_resume_invocations == 4
assert fake_runner.official_validation_after_selection is True
```

- [ ] **Step 2: Run focused pipeline tests and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_colab_pipeline.py -q`
Expected: FAIL because the entry point and stage runner are absent.

- [ ] **Step 3: Implement stage delegation and artifact gates**

Require CUDA before data access, execute integrity/augmentation/quick/comparison/selection/final/
validation/export/handoff in order, force and verify quick resume, validate required per-run files,
write parity and benchmark JSON, and skip only hash-valid completed outputs.

- [ ] **Step 4: Run pipeline and script-help tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_colab_pipeline.py tests/test_notebook_release.py -q`
Expected: PASS without requiring CUDA because command execution is injected.

### Task 5: Aggregate locked evaluation without image-level leakage

**Files:**
- Modify: `src/woundscope/evaluation.py`
- Modify: `scripts/evaluate.py`
- Create: `src/woundscope/results.py`
- Test: `tests/test_results_aggregation.py`

**Interfaces:**
- Consumes: completed per-seed official-validation aggregate reports plus frozen provenance/calibration.
- Produces: `aggregate_official_validation(reports) -> dict[str, Any]` with per-seed metrics, mean/median/SD/IQR, global metrics, three-seed mean and sample SD, 2,000-bootstrap CI metadata, confidence statistics, hashes, and no sample identifiers.

- [ ] **Step 1: Write failing aggregate/privacy tests**

```python
aggregate = aggregate_official_validation([seed42, seed43, seed44])
assert aggregate["seeds"] == [42, 43, 44]
assert aggregate["dice"]["ddof"] == 1
assert aggregate["bootstrap"]["samples"] == 2000
assert "sample_id" not in json.dumps(aggregate)
```

- [ ] **Step 2: Run aggregate tests and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_results_aggregation.py -q`
Expected: FAIL because `woundscope.results` does not exist.

- [ ] **Step 3: Implement strict frozen-report validation and recomputation**

Reject mixed models/losses/splits/source commits/config or manifest hashes, require all seeds,
recompute published means/sample SD from per-seed aggregate fields, retain negative differences,
and keep per-image CSV private.

- [ ] **Step 4: Run metrics/evaluation/aggregate tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_metrics.py tests/test_calibration_uncertainty.py tests/test_results_aggregation.py -q`
Expected: PASS.

### Task 6: Build privacy-safe source and result bundles

**Files:**
- Create: `src/woundscope/bundles.py`
- Create: `scripts/build_colab_bundle.py`
- Create: `scripts/verify_results_bundle.py`
- Test: `tests/test_bundles.py`

**Interfaces:**
- Produces: `build_source_bundle(repository, output)`, `build_result_bundle(artifact_root, output)`, and `verify_bundle(path, expected_kind, expected_source_commit)`.

- [ ] **Step 1: Write failing path-safety, allowlist, checksum, and privacy tests**

```python
manifest = verify_bundle(bundle, "results", "a" * 40)
names = {entry["path"] for entry in manifest["files"]}
assert not any(name.endswith((".onnx", ".safetensors", ".pt")) for name in names)
assert not any("per_image" in name or "sample_prediction" in name for name in names)
```

- [ ] **Step 2: Run bundle tests and confirm failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_bundles.py -q`
Expected: FAIL because bundle builders do not exist.

- [ ] **Step 3: Implement clean-snapshot source ZIP and safe aggregate handoff ZIP**

Normalize archive paths to POSIX, reject absolute/parent traversal, use explicit source roots and
result file classes, calculate size/SHA-256 inventory, reject secret/path patterns in JSON/YAML/text,
and verify every extracted member before accepting the ZIP.

- [ ] **Step 4: Run bundle and README updater tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_bundles.py tests/test_readme_results.py -q`
Expected: PASS.

### Task 7: Convert the notebook to a single thin launch wrapper

**Files:**
- Modify: `notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb`
- Modify: `scripts/download_artifacts.md`
- Test: `tests/test_notebook_release.py`

**Interfaces:**
- Consumes: `WoundScope_colab_source.zip`, `WOUNDSCOPE_DATA_DIR`, `WOUNDSCOPE_ARTIFACT_DIR`, and `scripts/run_colab_pipeline.py`.
- Produces: one Run-all path that mounts Drive, safe-extracts the committed bundle, verifies CUDA/source commit, installs dependencies, launches all stages, and prints the final safe ZIP path.

- [ ] **Step 1: Replace notebook expectations with failing thin-wrapper assertions**

```python
assert "RUN_MODE" not in sources
assert "FULL_STAGE" not in sources
assert "SELECTED_LOSS_UNET" not in sources
assert "scripts/run_colab_pipeline.py" in sources
assert "--cross-split-policy" not in sources
```

- [ ] **Step 2: Run notebook tests and confirm old manual-switch notebook fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_notebook_release.py -q`
Expected: FAIL because manual quick/comparison/final controls remain.

- [ ] **Step 3: Rewrite notebook cells as mount/load/install/verify/run/monitor only**

Set Drive targets to `MyDrive/WoundScope/WoundScope_colab_source.zip` and
`MyDrive/WoundScope/WoundScopeArtifacts/<source-commit-prefix>`, forbid CPU fallback, propagate the bundle source commit through an
environment variable, and invoke one staged command with no user-selected loss.

- [ ] **Step 4: Run notebook structure and JSON parse tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_notebook_release.py -q`
Expected: PASS.

### Task 8: Run local preflight and create the immutable Colab snapshot

**Files:**
- Modify: `PROGRESS.md`
- Generate ignored: `artifacts/handoff/WoundScope_colab_source.zip`

**Interfaces:**
- Consumes: committed branch snapshot and local pinned FUSeg checkout.
- Produces: exact PASS/FAIL evidence, a validated safe source ZIP, SHA-256, and immutable source commit.

- [ ] **Step 1: Run the M1 official-data gate**

Run: `.venv\Scripts\python.exe scripts/download_data.py --skip-download --allow-cross-split-exact`
Expected: PASS with 810 train, 200 validation, 200 test, zero test masks, seven train exclusions, retained validation 200, and seed-42 duplicate-group isolation.

- [ ] **Step 2: Run static and full CPU gates**

Run: `.venv\Scripts\python.exe -m ruff check .`
Run: `.venv\Scripts\python.exe -m ruff format --check .`
Run Mypy only if `pyproject.toml` contains a Mypy configuration.
Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all configured checks PASS without local CUDA use.

- [ ] **Step 3: Run ignore, secret, artifact, notebook, and synthetic vertical-slice audits**

Verify `.env`, data, manifests, checkpoints, weights, ONNX, TensorBoard, predictions, and galleries
are ignored; scan tracked files and candidate ZIP names/content without printing `.env`; confirm no
raw/source-derived image is tracked.

- [ ] **Step 4: Commit the staged Colab implementation**

Run: `git commit -m "feat(colab): automate resumable staged training handoff"`

- [ ] **Step 5: Build and verify the source ZIP from clean HEAD**

Run: `.venv\Scripts\python.exe scripts/build_colab_bundle.py --output artifacts/handoff/WoundScope_colab_source.zip --verify`
Expected: clean extraction passes package import, tests, notebook preflight, allowlist, file sizes,
checksums, path safety, and reports the current HEAD as source commit.

### Task 9: Execute Colab and recover verified results

**Files:**
- Private Drive: `MyDrive/WoundScope/WoundScope_colab_source.zip`
- Private Drive: `MyDrive/WoundScope/WoundScopeArtifacts/<source-commit-prefix>/`
- Local ignored: `artifacts/incoming/woundscope_colab_results_<run-id>.zip`

**Interfaces:**
- Consumes: immutable source ZIP and the notebook.
- Produces: a single checksum-bearing safe result ZIP or one consolidated `USER_ACTION_REQUIRED` handoff if interactive Google authorization blocks automation.

- [ ] **Step 1: Upload only the safe source ZIP and open the notebook in the signed-in Colab session**

Select T4, L4, or A100 GPU; do not inspect unrelated Drive content.

- [ ] **Step 2: Run all once and monitor the state record**

Expected order: integrity, quick, comparison, selection, final, official validation, ONNX/parity,
safe handoff. CUDA absence, a failed candidate, non-finite metric, compatibility mismatch, or missing
artifact stops the pipeline and remains recorded.

- [ ] **Step 3: Resume after runtime interruption using the same Run-all action**

Completed hash-valid stages and runs are skipped; incomplete compatible runs resume; completed run
directories are not overwritten.

- [ ] **Step 4: Download only the safe result ZIP**

Expected Drive path: `MyDrive/WoundScope/WoundScopeArtifacts/<source-commit-prefix>/handoff/woundscope_colab_results_<source-commit-prefix>.zip`.

### Task 10: Verify results and create the release candidate

**Files:**
- Modify: `README.md`
- Modify: `MODEL_CARD.md`
- Modify: `DATA_CARD.md`
- Modify: `PROGRESS.md`
- Create or modify: aggregate public charts under `reports/results/`.

**Interfaces:**
- Consumes: verified safe result ZIP only.
- Produces: recomputed public aggregate artifact accepted by `scripts/update_readme_results.py` and an evidence-backed release-candidate commit.

- [ ] **Step 1: Verify ZIP path safety, checksums, schema, and source commit**

Run: `$resultBundle = (Get-ChildItem artifacts\incoming\woundscope_colab_results_*.zip | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName; $sourceCommit = git rev-parse HEAD; .venv\Scripts\python.exe scripts\verify_results_bundle.py --bundle $resultBundle --expected-source-commit $sourceCommit --output artifacts\verified`
Expected: PASS; no sensitive/private member and no absolute Drive path.

- [ ] **Step 2: Recompute aggregates and update README through the guardrail**

Run: `.venv\Scripts\python.exe scripts/update_readme_results.py --results artifacts/verified/verified_results.json --readme README.md`
Expected: updater accepts only completed full, three-seed, official-validation results.

- [ ] **Step 3: Update cards/progress and generate fixed-rule aggregate charts**

Document all seeds and failed/negative runs, Colab hardware, hashes, locked calibration, duplicate
mitigation, confidence limits, and official-test/patient-wise/clinical limitations.

- [ ] **Step 4: Run full release, privacy, clean-export, and optional CPU Docker gates**

Run Ruff, format, full pytest, tracked-artifact/privacy scan, clean committed source export, and—if
the daemon is available—CPU Docker build plus app health smoke. Never invoke GPU Docker.

- [ ] **Step 5: Commit verified results or an honest negative result**

Run: `git commit -m "docs(results): publish verified WoundScope evaluation"`
If the experiment did not complete, commit only the blocker/negative evidence and do not populate
the README results marker.

- [ ] **Step 6: Confirm final local-only state**

Verify the requested branch, author, clean worktree, no remotes, and no push/tag/Release/Hugging Face deployment.
