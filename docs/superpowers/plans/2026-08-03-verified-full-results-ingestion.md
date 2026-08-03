# Verified Full Results Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the schema-valid c7 Colab full-run result bundle, publish only verified official-validation aggregates, and advance WoundScope milestones without exposing private model or image artifacts.

**Architecture:** Treat `woundscope_colab_results_c7ec6060f1bd.zip` as the immutable input. The existing bundle verifier checks manifest inventory, hashes, privacy, source commit, and aggregate schema; the existing README renderer recomputes per-seed means and bootstrap confidence intervals before touching marker content. Tracked documentation records only aggregate metrics and provenance, while the extracted 52-file evidence tree remains under gitignored `artifacts/`.

**Tech Stack:** Python 3.12, `woundscope.bundles`, `woundscope.readme_results`, Markdown, Ruff, pytest, Git.

## Global Constraints

- Official validation is the locked final evaluation split; official test has no public masks and receives no quantitative claims.
- The formal cross-split policy remains `exclude_train`: exclude seven exact training copies and retain all 200 official-validation images.
- Only schema-valid completed full-run results with seeds 42/43/44 and verified provenance may update public metrics.
- Do not track or publish FUSeg images, masks, image-level manifests, private galleries, checkpoints, ONNX models, TensorBoard files, or trainer states.
- Training source provenance remains `c7ec6060f1bd0a813a890b95b50c2855d3c2640c`; handoff implementation provenance remains `8345176593e3fe5a3c95e2f053306229e5a09455`.
- Keep model weights private pending manual data-license review. Do not configure remotes or push.

---

### Task 1: Verify and stage the immutable results evidence

**Files:**
- Consume: `C:/Users/3Hml/Downloads/woundscope_colab_results_c7ec6060f1bd.zip`
- Generate, gitignored: `artifacts/verified_downloaded_c7/`
- Inspect: `artifacts/verified_downloaded_c7/aggregate/verified_results.json`
- Inspect: `artifacts/verified_downloaded_c7/selection/loss_selection.json`
- Inspect: `artifacts/verified_downloaded_c7/aggregate/onnx_benchmark.json`

**Interfaces:**
- Consumes: result ZIP SHA-256 `6ff4d1f14f4242c72fa2ef3382bcbfadc15df93dd4aeb739ae1864f7de24f221`.
- Produces: a verified 52-file evidence tree and a rendered official-validation aggregate table.

- [x] **Step 1: Verify the downloaded ZIP hash**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\Users\3Hml\Downloads\woundscope_colab_results_c7ec6060f1bd.zip'
```

Expected: `6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221`.

- [x] **Step 2: Verify and extract the safe result bundle**

Run:

```powershell
.venv\Scripts\python.exe scripts\verify_results_bundle.py `
  --bundle 'C:\Users\3Hml\Downloads\woundscope_colab_results_c7ec6060f1bd.zip' `
  --expected-source-commit c7ec6060f1bd0a813a890b95b50c2855d3c2640c `
  --output artifacts\verified_downloaded_c7
```

Expected: `status=verified`, 52 files, matching training source commit.

- [x] **Step 3: Render aggregates through the production guardrail**

Run:

```powershell
@'
import json
from pathlib import Path
from woundscope.readme_results import render_results_table
payload = json.loads(Path('artifacts/verified_downloaded_c7/aggregate/verified_results.json').read_text(encoding='utf-8'))
print(render_results_table(payload))
'@ | .venv\Scripts\python.exe -
```

Expected rows:

```text
unet_efficientnet_b0 | bce_dice | 42/43/44 | Dice 0.8508±0.0035 (95% CI 0.8218–0.8768)
segformer_b0 | bce_dice | 42/43/44 | Dice 0.8270±0.0040 (95% CI 0.7973–0.8550)
```

### Task 2: Publish verified aggregate results and milestone evidence

**Files:**
- Modify: `README.md`
- Modify: `MODEL_CARD.md`
- Modify: `PROJECT_PLAN.md`
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: the verified aggregate table from Task 1.
- Produces: public official-validation metrics, weight-release status, source provenance, and evidence-backed milestone status.

- [x] **Step 1: Update only the guarded README marker region**

Run:

```powershell
.venv\Scripts\python.exe scripts\update_readme_results.py `
  --results artifacts\verified_downloaded_c7\aggregate\verified_results.json `
  --readme README.md --device cpu
```

Expected: the `RESULTS_TABLE_START/END` region contains two model rows and no `待填` marker.

- [x] **Step 2: Update README status and interpretation**

Replace the stale pre-training status with a statement that the full Colab run, locked official validation, six ONNX parity/benchmark runs, and safe handoff completed. State that U-Net has the higher observed Dice on this locked split, but do not claim test-set, clinical, patient-wise, or external-validation performance.

- [x] **Step 3: Update MODEL_CARD from the same verified table**

Record both three-seed rows with mean±SD and Dice bootstrap CI, the private-weight status, the c7 training source commit, the repair implementation commit, and the safe result ZIP SHA-256. Keep every medical-use limitation intact.

- [x] **Step 4: Advance only evidence-backed milestones in PROGRESS**

Mark M3, M4, and M5 `Completed` because the Colab quick/full/resume, locked evaluation/calibration/gallery, CUDA/ONNX parity/CPU benchmark, and app tests now have artifacts. Keep M6 `In review` pending the final release/clean-reproduction audit. Add exact bundle, source, metrics, privacy, and test evidence; remove stale blockers and stale "no model artifacts" statements.

- [x] **Step 5: Refresh the non-normative project status line**

Update only the `PROJECT_PLAN.md` header status from "Colab formal experiment pending" to "formal experiment and safe handoff completed; M6 release review in progress". Do not alter locked protocol or Decision Log entries.

### Task 3: Run release gates and create the local milestone commit

**Files:**
- Verify: `README.md`
- Verify: `MODEL_CARD.md`
- Verify: `PROGRESS.md`
- Verify: repository tracked inventory
- Modify: `tests/test_notebook_release.py`

**Interfaces:**
- Consumes: Task 2 documentation changes.
- Produces: a clean, locally committed milestone boundary with no remote publication.

- [x] **Step 1: Re-run the result renderer and schema tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_readme_results.py tests\test_bundles.py tests\test_results_aggregation.py -q
```

Expected: all focused tests pass.

- [x] **Step 2: Run the complete repository gate**

Run:

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
git diff --check
```

Expected: Ruff, format, all tests, and whitespace checks pass; only documented legacy ONNX exporter warnings may remain.

- [x] **Step 3: Audit privacy and publication boundaries**

Confirm the tracked tree contains no `.env`, medical images/masks, image-level manifests, checkpoints, ONNX files, private galleries, TensorBoard files, or trainer states. Confirm `git remote` is empty and the extracted result evidence remains ignored.

- [x] **Step 4: Commit the milestone boundary locally**

Run:

```powershell
git add README.md MODEL_CARD.md PROJECT_PLAN.md PROGRESS.md tests/test_notebook_release.py docs/superpowers/plans/2026-08-03-verified-full-results-ingestion.md
git commit -m "docs(results): publish verified c7 full-run metrics"
```

Expected: a local commit on `portfolio/woundscope-colab-full-run`; no push and no remote creation.
