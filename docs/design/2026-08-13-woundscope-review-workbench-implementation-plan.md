# WoundScope Review Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portfolio-grade zh-TW React review workbench backed by a privacy-safe FastAPI boundary while preserving the existing WoundScope scientific inference contract.

**Architecture:** A Vite-built React SPA owns layout, interaction, and browser-only preview state. FastAPI exposes health, model-readiness, and single-image prediction endpoints through an injected runtime protocol; the default runtime lazily reuses the existing ONNX predictor and never exposes private artifact paths. A multi-stage Docker image builds the SPA and serves it from the Python application.

**Tech Stack:** Python 3.11–3.12, FastAPI, Pydantic, Uvicorn, Pillow, ONNX Runtime, React, TypeScript, Vite, Vitest, Testing Library, axe-core, pnpm 11.16.0, Node.js 24.

## Global Constraints

- Work only in the canonical checkout and branch `codex/ui-review-workbench`; do not create a clone or worktree.
- Human-readable copy is zh-TW-first; retain technical proper nouns in English.
- Desktop body text is at least 17px with line-height at least 1.55; secondary copy is at least 15px; interactive targets are at least 44×44px.
- Preserve the existing model family, threshold, calibration, confidence, TTA, metrics, and official-validation semantics.
- Never add diagnosis, severity, prognosis, or treatment recommendations.
- Never track or upload FUSeg images/masks, image-level manifests, weights, ONNX, checkpoints, private galleries, filenames, secrets, or absolute local paths.
- Model-backed public deployment remains `PERMISSION_PENDING`; the default public state is code-only showcase mode.
- Inference accepts one local upload only and does not persist request images or log original filenames.
- Use CSS custom properties for semantic color tokens and keep WCAG AA text contrast.
- Support 390×844, 1024×768, and 1440×900 without horizontal overflow or clipped controls.
- Every production behavior follows RED → GREEN → REFACTOR; synthetic fixtures only.
- Commit author and committer must be `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` with no co-author trailers.

---

## File Structure

```text
frontend/
├── index.html, package.json, pnpm-lock.yaml
├── tsconfig.json, tsconfig.node.json, vite.config.ts
└── src/
    ├── main.tsx
    ├── app/App.tsx, app/App.test.tsx
    ├── components/{Header,EvidenceStrip,ResearchShowcase,ProvenancePanel,SafetyFooter}.tsx
    ├── features/review/{ReviewWorkspace,ImageStage,ResultRail,useReviewSession}.ts(x)
    ├── lib/api/{client,client.test,types}.ts
    ├── styles/{tokens,index}.css
    └── test/setup.ts
src/woundscope/model_runtime.py
src/woundscope/review_api.py
tests/test_model_runtime.py
tests/test_review_api.py
reports/public/woundscope-ui-showcase.webp
```

`model_runtime.py` owns artifact resolution and readiness. `review_api.py` owns HTTP validation and response sanitation. Frontend state, visual components, and API types remain separated so no component knows Python or ONNX details.

---

### Task 1: Shared model runtime and safe readiness status

**Files:**
- Create: `src/woundscope/model_runtime.py`
- Create: `tests/test_model_runtime.py`
- Modify: `src/woundscope/gradio_app.py`
- Test: `tests/test_onnx_inference_app.py`

**Interfaces:**
- Consumes: `OnnxPredictor`, `CalibrationArtifact`, artifact and pinned Hugging Face environment variables.
- Produces: `RuntimeMode`, `ModelStatus`, `resolve_model_artifacts()`, `inspect_model_status()`, `load_predictor()`.

- [ ] **Step 1: Write the failing tests**

```python
def test_missing_model_reports_showcase_without_private_path(monkeypatch, tmp_path):
    private = tmp_path / "private" / "model.onnx"
    monkeypatch.setenv("WOUNDSCOPE_MODEL_PATH", str(private))
    status = inspect_model_status()
    assert status.mode is RuntimeMode.SHOWCASE
    assert status.model_available is False
    assert str(private) not in status.message


def test_ready_artifacts_report_local_review(monkeypatch, tmp_path):
    model = tmp_path / "model.onnx"
    calibration = tmp_path / "calibration.json"
    model.write_bytes(b"synthetic")
    calibration.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("WOUNDSCOPE_MODEL_PATH", str(model))
    monkeypatch.setenv("WOUNDSCOPE_CALIBRATION_PATH", str(calibration))
    status = inspect_model_status()
    assert status.mode is RuntimeMode.LOCAL_REVIEW
    assert status.model_available and status.calibration_available
```

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\test_model_runtime.py -q`

Expected: collection fails because `woundscope.model_runtime` does not exist.

- [ ] **Step 3: Implement minimal runtime**

```python
class RuntimeMode(StrEnum):
    SHOWCASE = "showcase"
    LOCAL_REVIEW = "local_review"


@dataclass(frozen=True)
class ModelStatus:
    mode: RuntimeMode
    model_available: bool
    calibration_available: bool
    model_label: str
    provider: str
    message: str
```

Move immutable revision validation and artifact download handling from Gradio. `inspect_model_status()` checks file availability without opening ONNX and never interpolates a path. `load_predictor()` remains cached. Preserve `_resolve_model_artifacts` and `_load_predictor` aliases in `gradio_app.py` for compatibility.

- [ ] **Step 4: Verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests\test_model_runtime.py tests\test_onnx_inference_app.py -q`

Expected: all selected tests pass, including pinned-revision and token-suppression cases.

- [ ] **Step 5: Commit**

```powershell
git add src/woundscope/model_runtime.py src/woundscope/gradio_app.py tests/test_model_runtime.py
git commit -m "refactor: share safe model runtime"
```

---

### Task 2: FastAPI health, readiness, and prediction contract

**Files:**
- Create: `src/woundscope/review_api.py`
- Create: `tests/test_review_api.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: `ModelStatus`, `inspect_model_status()`, `load_predictor()`, `PredictionResult`, `create_overlay()`.
- Produces: `ReviewRuntime`, `create_app(runtime=None, frontend_dir=None)`, `/api/health`, `/api/model-status`, `/api/predict`.

- [ ] **Step 1: Write failing API tests with a synthetic runtime**

```python
def test_predict_returns_in_memory_assets_and_nonclinical_metrics():
    client = TestClient(create_app(runtime=SyntheticRuntime()))
    response = client.post(
        "/api/predict",
        files={"image": ("synthetic.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overlay_data_url"].startswith("data:image/png;base64,")
    assert body["mask_data_url"].startswith("data:image/png;base64,")
    assert body["confidence_label"] == "模型分割信心，非臨床信心"
```

Also test health/version without predictor loading; status fields `mode`, `model_available`, `calibration_available`, safe model label/hash prefix, provider, and readiness message; model-unavailable `503 MODEL_NOT_AVAILABLE`; invalid bytes `422 INVALID_IMAGE`; input above 12 MiB `413 IMAGE_TOO_LARGE`; dimensions above 8192 `422`; and an inference exception containing path/token sentinels returning only `500 INFERENCE_FAILED` without sentinel disclosure.

- [ ] **Step 2: Add API dependencies and verify behavioral RED**

Add `fastapi>=0.116,<1`, `uvicorn[standard]>=0.35,<1`, and `python-multipart>=0.0.20,<1` to the `app` extra; update the lockfile. Run `.venv\Scripts\python.exe -m pytest tests\test_review_api.py -q`.

Expected: tests fail because the routes are absent.

- [ ] **Step 3: Implement the API**

```python
class ReviewRuntime(Protocol):
    def status(self) -> ModelStatus: ...
    def predict(self, image: Image.Image) -> PredictionResult: ...


def create_app(
    runtime: ReviewRuntime | None = None,
    frontend_dir: Path | None = None,
) -> FastAPI: ...
```

Accept only PNG/JPEG/WebP multipart uploads, decode with Pillow in memory, normalize to RGB, reuse `create_overlay`, and encode overlay/mask with `BytesIO`. Do not log or return `UploadFile.filename`; do not write request bodies to disk. Known errors return `detail.code` and `detail.message`; unexpected inference failures use a fixed message and `raise ... from None`. JSON fields remain snake_case and frontend types match them exactly.

- [ ] **Step 4: Verify GREEN**

Run: `.venv\Scripts\python.exe -m pytest tests\test_review_api.py tests\test_model_runtime.py tests\test_onnx_inference_app.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml uv.lock src/woundscope/review_api.py tests/test_review_api.py
git commit -m "feat: add privacy-safe review API"
```

---

### Task 3: React foundation and research showcase mode

**Files:**
- Create: `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/index.html`
- Create: `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`, `frontend/src/app/App.tsx`, `frontend/src/app/App.test.tsx`
- Create: `frontend/src/components/Header.tsx`, `EvidenceStrip.tsx`, `ResearchShowcase.tsx`, `ProvenancePanel.tsx`, `SafetyFooter.tsx`
- Create: `frontend/src/lib/api/types.ts`, `client.ts`, `client.test.ts`
- Create: `frontend/src/styles/tokens.css`, `index.css`, `frontend/src/test/setup.ts`

**Interfaces:**
- Consumes: `GET /api/model-status`.
- Produces: `ModelStatus`, `ApiError`, `fetchModelStatus()`, accessible showcase shell and shared design tokens.

- [ ] **Step 1: Add tooling configuration and failing tests**

Pin `packageManager` to `pnpm@11.16.0`, `engines.node` to `>=24 <25`, and scripts `dev`, `build`, `lint`, `typecheck`, `test`, `test:run`. Use React, React DOM, Lucide React, TypeScript, Vite, Vitest, jsdom, Testing Library, jest-dom, axe-core, eslint, typescript-eslint, and eslint-plugin-react-hooks.

```tsx
it("renders verified evidence in permission-aware showcase mode", async () => {
  mockStatus({ mode: "showcase", model_available: false });
  render(<App />);
  expect(await screen.findByText("研究展示模式")).toBeVisible();
  expect(screen.getByText("0.8508")).toBeVisible();
  expect(screen.getByText(/Official Validation · 200 張/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "開始分割複核" })).not.toBeInTheDocument();
});
```

Add client tests for a valid status response, structured API error, and network failure.

- [ ] **Step 2: Install and verify RED**

Run from `frontend/`: `pnpm install --frozen-lockfile=false`, then `pnpm test:run`.

Expected: tests fail because `App`, client, and components are missing.

- [ ] **Step 3: Implement the showcase shell**

Use only verified public evidence already in README: U-Net Dice `0.8508 ± 0.0035`, 200 Official Validation images, 3 seeds, and two model families. Every value has a scope label. `ResearchShowcase` uses an inline SVG contour/grid marked decorative; it does not resemble or claim to be a patient image.

```css
:root {
  --canvas: #f4f1ea;
  --surface: #fbfaf7;
  --ink: #24313a;
  --muted-ink: #5e6a6f;
  --primary: #667f73;
  --secondary: #8ea6af;
  --accent: #c77862;
  --review: #9a6a2d;
  --success: #4e7562;
  --font-sans: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif;
  --font-serif: "Noto Serif TC", "Songti TC", "PMingLiU", serif;
  --body-size: 17px;
}
```

Do not fetch fonts or analytics. Use one compact header with WoundScope, status, GitHub, MODEL_CARD, and DATA_CARD links; one evidence strip; the main showcase/workspace region; one safe provenance disclosure; and one safety footer. Theme control uses a labeled button and persists only the non-sensitive display preference in browser storage.

- [ ] **Step 4: Verify GREEN**

Run from `frontend/`:

```powershell
pnpm test:run
pnpm typecheck
pnpm lint
pnpm build
```

Expected: all commands exit 0, `dist/index.html` exists, and showcase axe test has zero violations.

- [ ] **Step 5: Commit**

```powershell
git add frontend
git commit -m "feat: build research showcase frontend"
```

---

### Task 4: Local image review workflow and comparison controls

**Files:**
- Create: `frontend/src/features/review/useReviewSession.ts`
- Create: `frontend/src/features/review/ReviewWorkspace.tsx`, `ReviewWorkspace.test.tsx`
- Create: `frontend/src/features/review/ImageStage.tsx`, `ResultRail.tsx`
- Modify: `frontend/src/app/App.tsx`, `frontend/src/styles/index.css`
- Modify: `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/types.ts`

**Interfaces:**
- Consumes: `POST /api/predict`, browser `File`, object URL, and AbortController.
- Produces: `ReviewState = empty | ready | loading | result | error`, `submitPrediction(file)`, before/after slider, original/overlay/mask modes, opacity control.

- [ ] **Step 1: Write failing workflow tests**

```tsx
it("uploads only after explicit action and renders nonclinical results", async () => {
  const user = userEvent.setup();
  render(<ReviewWorkspace status={readyStatus} />);
  await user.upload(screen.getByLabelText("選擇影像"), syntheticPngFile());
  expect(predictSpy).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "開始分割複核" }));
  expect(await screen.findByText("模型分割信心，非臨床信心")).toBeVisible();
  expect(screen.getByText("需人工複核")).toBeVisible();
});


it("switches layers and exposes the opacity value", async () => {
  renderResultState();
  await userEvent.click(screen.getByRole("button", { name: "Mask" }));
  expect(screen.getByTestId("mask-layer")).toBeVisible();
  expect(screen.getByRole("slider", { name: "Overlay 透明度" })).toHaveValue("45");
});
```

Also test invalid MIME feedback next to the field, disabled action while loading, object URL revocation on replacement/unmount, sanitized server-error recovery, keyboard comparison slider, fullscreen entry/exit, and review reason expressed as text rather than color alone.

- [ ] **Step 2: Verify RED**

Run: `pnpm --dir frontend test:run -- ReviewWorkspace.test.tsx`

Expected: fails because review components and state machine are absent.

- [ ] **Step 3: Implement the workflow**

Keep original preview as a browser object URL and submit only on explicit action. The comparison slider clips overlay with a percentage custom property; view buttons use `aria-pressed`; opacity is a labeled range from 20 to 80 with default 45; fullscreen keeps the same controls and keyboard behavior. The mask uses translucent fill plus a contour treatment so meaning never depends on color alone. Replacing the image aborts an active request, revokes the previous object URL, and clears stale output.

Result cards show ratio, percentage confidence, inference milliseconds/provider, and review status. Confidence always reads `模型分割信心，非臨床信心`; ratio never uses severity language.

- [ ] **Step 4: Verify GREEN**

```powershell
pnpm --dir frontend test:run
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src
git commit -m "feat: add segmentation review workspace"
```

---

### Task 5: Static hosting, local entry point, and Docker integration

**Files:**
- Modify: `src/woundscope/review_api.py`, `tests/test_review_api.py`
- Modify: `app/app.py`, `Dockerfile`, `.dockerignore`
- Test: `tests/test_huggingface_space_bundle.py`

**Interfaces:**
- Consumes: `frontend/dist`, `create_app()`.
- Produces: SPA fallback for non-API routes, `app.app:app`, port 7860, production container.

- [ ] **Step 1: Write failing hosting tests**

```python
def test_frontend_shell_is_served_without_loading_model(tmp_path):
    (tmp_path / "index.html").write_text(
        "<main>WoundScope shell</main>", encoding="utf-8"
    )
    client = TestClient(create_app(runtime=ShowcaseRuntime(), frontend_dir=tmp_path))
    assert client.get("/").text == "<main>WoundScope shell</main>"
    assert client.get("/review").text == "<main>WoundScope shell</main>"
    assert client.get("/api/missing").status_code == 404
```

Add a release test that `app/app.py` exposes a FastAPI object and does not launch Gradio at import.

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\test_review_api.py tests\test_huggingface_space_bundle.py -q`

Expected: SPA and entry-point assertions fail.

- [ ] **Step 3: Implement static hosting and container build**

Serve hashed assets with `StaticFiles`, return `index.html` for non-API browser routes, and keep `/api/*` missing routes as JSON 404. `app/app.py` exposes `app = create_app()` and runs Uvicorn only under the main guard.

```dockerfile
FROM node:24-alpine AS frontend-build
WORKDIR /workspace/frontend
RUN corepack enable && corepack prepare pnpm@11.16.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2,<3" \
    && pip install --no-cache-dir ".[app,export]"
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist
EXPOSE 7860
CMD ["python", "app/app.py"]
```

Keep Gradio source/package compatibility for code-only bundle tests, but make FastAPI the primary container UI.

- [ ] **Step 4: Verify GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests\test_review_api.py tests\test_huggingface_space_bundle.py tests\test_onnx_inference_app.py -q
pnpm --dir frontend build
docker build -t woundscope:ui-review .
docker run --rm woundscope:ui-review python -c "from app.app import app; print(type(app).__name__)"
```

Expected: tests/build succeed and the container prints `FastAPI`; no model load or download occurs.

- [ ] **Step 5: Commit**

```powershell
git add src/woundscope/review_api.py tests/test_review_api.py app/app.py Dockerfile .dockerignore
git commit -m "feat: serve review workbench with FastAPI"
```

---

### Task 6: CI and exact screenshot privacy gates

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `src/woundscope/repository_privacy.py`
- Modify: `tests/test_repository_privacy.py`
- Modify: `tests/test_release_metadata.py`

**Interfaces:**
- Consumes: frontend scripts and exact screenshot path.
- Produces: `frontend-tests` CI job, three-job required gate, exact non-medical screenshot allowlist.

- [ ] **Step 1: Write failing CI and privacy tests**

```python
assert set(jobs) == {
    "python-311-tests", "python-312-build", "frontend-tests", "synthetic-gates"
}
assert str(frontend_job["steps"][1]["uses"]).startswith(
    "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e"
)
assert frontend_job["steps"][1]["with"]["node-version"] == "24"
for command in (
    "pnpm install --frozen-lockfile", "pnpm test:run", "pnpm typecheck",
    "pnpm lint", "pnpm build",
):
    assert command in frontend_commands
assert set(required_gate["needs"]) == {
    "python-311-tests", "python-312-build", "frontend-tests"
}
```

Add privacy tests that allow only case-sensitive `reports/public/woundscope-ui-showcase.webp` and continue rejecting every other PNG/JPEG/WebP path, including similarly named files outside `reports/public`.

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\test_repository_privacy.py tests\test_release_metadata.py -q`

Expected: CI job-set and raster allowlist assertions fail.

- [ ] **Step 3: Implement CI and privacy contracts**

Add `frontend-tests` using SHA-pinned `actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e # v6.4.0`, Node 24, `package-manager-cache: false`, Corepack pnpm 11.16.0, frozen install, tests, typecheck, lint, and build. Add `FRONTEND_RESULT` to `synthetic-gates`.

In the privacy audit, allow one exact path only; do not allow a directory or extension class. The screenshot must be captured from showcase mode with no upload and no model artifact.

- [ ] **Step 4: Verify GREEN**

```powershell
.venv\Scripts\python.exe -m pytest tests\test_repository_privacy.py tests\test_release_metadata.py -q
.venv\Scripts\python.exe scripts\audit_repository_privacy.py --repository .
```

Expected: tests pass and audit reports zero violations before the screenshot is staged.

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/ci.yml src/woundscope/repository_privacy.py tests/test_repository_privacy.py tests/test_release_metadata.py
git commit -m "ci: verify review workbench frontend"
```

---

### Task 7: Browser verification, public screenshot, and README presentation

**Files:**
- Create: `reports/public/woundscope-ui-showcase.webp`
- Modify: `README.md`, `tests/test_release_metadata.py`
- Modify if a viewport test reproduces a defect: `frontend/src/styles/index.css`, `tokens.css`

**Interfaces:**
- Consumes: built frontend and FastAPI showcase mode.
- Produces: responsive verified UI, privacy-safe README visual, new local startup instructions.

- [ ] **Step 1: Write failing README assertions**

```python
def test_readme_presents_review_workbench_without_model_overclaim():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "reports/public/woundscope-ui-showcase.webp" in readme
    assert "React + TypeScript + Vite" in readme
    assert "FastAPI" in readme
    assert "研究展示模式" in readme
    assert "模型可用時才開啟本機分割複核" in readme
    assert "啟動本機 Gradio Web UI" not in readme
```

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py::test_readme_presents_review_workbench_without_model_overclaim -q`

Expected: fails because the screenshot and copy are absent.

- [ ] **Step 3: Run browser viewport gates**

Build the frontend, start `app/app.py` without model environment variables, then inspect:

- 1440×900 desktop
- 1024×768 tablet
- 390×844 mobile

For each viewport verify no horizontal scroll, no clipped text, computed body font ≥17px desktop and ≥16px mobile, secondary copy ≥15px, controls ≥44px, visible focus, AA light/dark contrast, correct showcase status, no upload form, labeled theme control, reduced-motion behavior, and no console errors. Apply a CSS change only after reproducing a failure, then re-run that viewport.

- [ ] **Step 4: Capture and audit the screenshot**

Capture the 1440×900 showcase state as `reports/public/woundscope-ui-showcase.webp`. Inspect original resolution and verify: no medical image/mask, filename, artifact path, token, personal data, misleading prediction, browser chrome, or debug overlay. Stage it and run the privacy audit so the exact allowlist is exercised.

- [ ] **Step 5: Update README and verify GREEN**

Replace `Local Gradio` positioning with the React/FastAPI workbench, embed the screenshot near the hero, document showcase/local-review modes, and preserve result provenance, Colab, Space permission, cards, and release links. Local commands are `pnpm --dir frontend build` then `.venv\Scripts\python.exe app\app.py`.

```powershell
.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py -q
.venv\Scripts\python.exe scripts\audit_repository_privacy.py --repository .
git diff --check
```

Expected: all exit 0 and privacy audit reports zero violations including the screenshot.

- [ ] **Step 6: Commit**

```powershell
git add README.md reports/public/woundscope-ui-showcase.webp tests/test_release_metadata.py frontend/src/styles
git commit -m "docs: present the review workbench UI"
```

---

### Task 8: Full gate, progress evidence, and final review

**Files:**
- Modify: `PROGRESS.md` (local control/evidence asset; remains ignored)

**Interfaces:**
- Consumes: complete branch.
- Produces: exact PASS/FAIL evidence, clean branch, preserved user-facing preview.

- [ ] **Step 1: Run complete Python gates**

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\audit_repository_privacy.py --repository .
git diff --check
```

Record exact test count, warnings, audit count, and failures. Do not claim completion if any command exits nonzero.

- [ ] **Step 2: Run complete frontend gates**

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend test:run
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Record exact test count and build output. No console or test error is accepted.

- [ ] **Step 3: Run packaging and container gates**

```powershell
uv build --out-dir dist
docker build -t woundscope:ui-review .
docker run --rm woundscope:ui-review python -c "from app.app import app; print('FASTAPI_CONTAINER_SMOKE_PASS', type(app).__name__)"
```

Do not launch a model-backed container, use GPU, download model artifacts, or expose a public port.

- [ ] **Step 4: Re-run browser inspection**

Verify showcase mode at all three viewports. Use a synthetic injected runtime for local-review state and exercise upload → loading → result → original/overlay/mask → opacity → replacement → error recovery. Confirm no console errors and preserve the user-facing tab.

- [ ] **Step 5: Update local progress evidence**

Add a 2026-08-13 `PROGRESS.md` entry with scope, branch/commit range, commands, exact results, screenshot, privacy boundaries, absence of GPU/training/deployment, remaining `PERMISSION_PENDING`, and next action. Do not stage `PROGRESS.md`.

- [ ] **Step 6: Audit branch identity and inventory**

```powershell
git status --short --branch
git log main..HEAD --format="%H%n%an <%ae>%n%cn <%ce>%n%B"
git diff --stat main...HEAD
git diff --name-only main...HEAD
git ls-files | Select-String -Pattern '\.(onnx|pt|pth|safetensors|png|jpg|jpeg)$'
```

Expected: owner identity only, no co-author trailers, no private/model artifacts, and only the exact allowlisted WebP raster.

- [ ] **Step 7: Request code review and fix verified findings**

Use the requesting-code-review workflow against `main...HEAD`. For each actionable finding, add a failing regression test, reproduce RED, implement the smallest fix, and rerun focused plus full gates.

- [ ] **Step 8: Commit verified review corrections**

If review produces tracked changes, stage only those files, rerun staged privacy/diff checks, and commit:

```powershell
git commit -m "fix: harden review workbench delivery"
```

Do not push, create a pull request, tag, publish, or deploy without a new explicit user instruction.
