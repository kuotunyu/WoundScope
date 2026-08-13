# WoundScope Scientific Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the existing WoundScope showcase and review workspace into a rational, compact Scientific Console with balanced typography, less empty space, and functional borders only.

**Architecture:** Preserve the existing React component and FastAPI boundaries. Update semantic copy and grouping in the four showcase components, then centralize the denser typography／shape decisions in the existing CSS tokens and stylesheet. Keep all verified evidence, API behavior, local-review interactions, privacy boundaries, and scientific semantics unchanged.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, axe-core, CSS custom properties, FastAPI, Python 3.11–3.12.

## Global Constraints

- Work only in the canonical checkout on `codex/ui-review-workbench`; do not create a clone or worktree.
- Human-readable copy is zh-TW-first; technical proper nouns remain in English.
- Showcase H1 is `WoundScope 傷口分割複核工作台`; desktop 38–42px, tablet 34–38px, mobile 30–34px, sans-serif.
- Desktop body text is 18px; mobile body text is 17px; visible metadata is at least 16px.
- Interactive targets remain at least 44×44px.
- Radius tokens are small 4px, medium 6px, large 8px.
- Full borders remain only on the research plate, upload dropzone, image canvas, fullscreen stage, and primary actions.
- Preserve every verified aggregate, status fact, provenance fact, safety statement, API field, and review interaction.
- Do not change scientific protocol, metrics, model behavior, calibration, threshold, confidence semantics, or artifact policy.
- Do not add or track medical images, masks, weights, ONNX, filenames, private paths, galleries, secrets, or image-level artifacts.
- Do not push, deploy, train, publish model artifacts, or change `PERMISSION_PENDING`.
- Use RED → GREEN → REFACTOR for component behavior; use bounded desktop／tablet／mobile browser checks for visual contracts.
- Git author and committer remain `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` without trailers.

---

## File Structure

```text
frontend/src/app/App.test.tsx
frontend/src/components/ResearchShowcase.tsx
frontend/src/components/ProvenancePanel.tsx
frontend/src/components/EvidenceStrip.tsx
frontend/src/features/review/ReviewWorkspace.tsx
frontend/src/styles/tokens.css
frontend/src/styles/index.css
design-system/woundscope/MASTER.md
reports/public/woundscope-ui-showcase.webp
PROGRESS.md  # local ignored evidence only
```

No new runtime module or dependency is required. `ResearchShowcase` owns the compact research summary and inline mode status. `EvidenceStrip` and `ProvenancePanel` remain semantic information rails. CSS owns the shared typography, spacing, radius, divider, and responsive contracts.

---

### Task 1: Lock the rational content hierarchy

**Files:**
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/components/ResearchShowcase.tsx`
- Modify: `frontend/src/components/ProvenancePanel.tsx`

**Interfaces:**
- Consumes: existing `ModelStatus`, verified aggregate copy, and showcase error state.
- Produces: compact H1, inline `role="status"`, direct provenance heading, unchanged four-term definition list.

- [ ] **Step 1: Write failing semantic regressions**

```tsx
it("frames the showcase as a scientific workbench instead of an editorial headline", async () => {
  mockStatus();
  const { container } = render(<App />);
  await screen.findByText("研究展示模式");

  expect(
    screen.getByRole("heading", {
      level: 1,
      name: "WoundScope 傷口分割複核工作台",
    }),
  ).toBeVisible();
  expect(screen.queryByText(/從像素預測/)).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveClass("mode-status");
  expect(container.querySelector(".mode-panel")).toBeNull();
});

it("uses direct provenance language without dropping evidence", async () => {
  mockStatus();
  render(<App />);
  const region = await screen.findByRole("region", { name: "Artifact 與研究來源" });
  expect(within(region).getAllByRole("term")).toHaveLength(4);
  expect(screen.queryByText(/每個結果/)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Verify RED**

Run: `pnpm --dir frontend test:run -- src/app/App.test.tsx`

Expected: the new H1, `mode-status`, and direct provenance heading assertions fail against the current editorial copy and `mode-panel` markup.

- [ ] **Step 3: Implement the minimal semantic change**

Use the exact H1 `WoundScope 傷口分割複核工作台`. Replace the two-line slogan with one concise explanation of data integrity, segmentation, calibration, ONNX parity, and provenance. Rename `.mode-panel` to `.mode-status`, use `role="status" aria-live="polite"`, and keep the existing safe error／showcase messages. Change the provenance eyebrow to `RESEARCH PROVENANCE` and H2 to `Artifact 與研究來源`; retain release, model artifact, calibration, permission, and disclosure paragraphs verbatim.

- [ ] **Step 4: Verify GREEN**

Run: `pnpm --dir frontend test:run -- src/app/App.test.tsx`

Expected: all App tests pass, including axe and permission-aware showcase assertions.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/app/App.test.tsx frontend/src/components/ResearchShowcase.tsx frontend/src/components/ProvenancePanel.tsx
git commit -m "refactor: clarify scientific workbench hierarchy"
```

---

### Task 2: Distill typography, space, borders, and radius

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/index.css`
- Modify: `frontend/src/features/review/ReviewWorkspace.tsx`
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `design-system/woundscope/MASTER.md`

**Interfaces:**
- Consumes: existing component class names and the Task 1 `mode-status` class.
- Produces: 18px desktop／17px mobile type scale, 4／6／8px radius tokens, compact first viewport, divider-based evidence and provenance rails.

- [ ] **Step 1: Add a failing local-review heading regression**

```tsx
expect(
  await screen.findByRole("heading", {
    level: 1,
    name: "WoundScope 傷口分割複核工作台",
  }),
).toBeVisible();
```

Run: `pnpm --dir frontend test:run -- src/app/App.test.tsx`

Expected: local-review mode still renders `傷口分割複核工作台`, so the new shared rational heading assertion fails.

- [ ] **Step 2: Implement the shared heading copy**

Change only the local-review H1 to `WoundScope 傷口分割複核工作台`. Keep upload, result, confidence, review warning, and provider copy unchanged.

- [ ] **Step 3: Implement the visual contract**

Update tokens to:

```css
--body-size: 18px;
--radius-sm: 4px;
--radius-md: 6px;
--radius-lg: 8px;
```

Then make these bounded stylesheet changes:

- `main`: 24–32px top padding and 16–20px section gap.
- `.showcase`: top-aligned 5/7 desktop grid; remove copy vertical centering.
- Showcase H1 and workspace H1: sans-serif, 38–42px desktop, maximum 34px mobile.
- `.lede`, status copy, evidence labels, provenance labels, footer, review helpers: 16px minimum; main explanatory copy 17–18px.
- `.mode-status`: inline grid with one top rule, no card background, radius, shadow, or enclosing border.
- `.research-plate`: 360–390px desktop, one border, 8px radius, no inset pseudo-frame or main shadow; scale SVG accordingly.
- `.evidence-strip`: top/bottom rules only, no surface card or outer radius; retain column dividers.
- `.provenance`: top rule, no outer background, shadow, radius, or enclosing border; retain semantic grid dividers.
- Header navigation links become flat 6px controls; reserve pills for status/segmented controls only.
- Review workspace keeps borders only where the interaction or image plane needs a boundary; remove redundant result-rail and nested metric card radii when dividers communicate the grouping.
- Mobile `--body-size` becomes 17px; the abstract plate is at most about 300px and H1 30–34px.

Update `MASTER.md` direction to `Scientific Console／理性研究台`, type floors to 18／17／16px, radius to 4／6／8px, and functional-border rules. Do not change colors or motion policy.

- [ ] **Step 4: Verify component GREEN**

```powershell
pnpm --dir frontend test:run
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: 0 failures and a successful production bundle.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src design-system/woundscope/MASTER.md
git commit -m "refactor: distill scientific console layout"
```

---

### Task 3: Run bounded visual inspection and fix one batch

**Files:**
- Modify if inspection reproduces a defect: `frontend/src/styles/index.css`
- Modify if inspection reproduces a defect: `frontend/src/styles/tokens.css`

**Interfaces:**
- Consumes: production Vite bundle served by the existing FastAPI app.
- Produces: verified desktop, tablet, mobile, light, and dark presentation without overflow or tiny text.

- [ ] **Step 1: Build and reload the existing local server**

Run `pnpm --dir frontend build`, then reload `http://127.0.0.1:7863/`. Do not set model environment variables.

- [ ] **Step 2: Inspect one batched round**

At 1440×900, 1024×768, 390×844, and 375px verify:

- no horizontal overflow or clipped copy;
- computed body text is 18px desktop and 17px mobile;
- no visible secondary text below 16px;
- no interactive target below 44×44px;
- H1 is sans-serif and within the approved size range;
- desktop first viewport includes the summary, research plate, and start of verified evidence;
- mode status, evidence, and provenance are divider-based rather than cards;
- dark theme keeps readable contrast without relying on surface-card backgrounds;
- console has no error／warning entries.

- [ ] **Step 3: Apply one consolidated correction batch**

Only fix defects reproduced in Step 2. Keep changes inside the two stylesheet files unless a semantic defect requires the owning component. Do not add visual features.

- [ ] **Step 4: Confirm once**

Repeat the affected viewports only. Stop after the confirmation pass; do not enter open-ended polishing.

- [ ] **Step 5: Run the design detector once**

```powershell
node C:\Users\3Hml\.codex\skills\impeccable\scripts\detect.mjs --json frontend/src/components/ResearchShowcase.tsx frontend/src/components/ProvenancePanel.tsx frontend/src/features/review/ReviewWorkspace.tsx frontend/src/styles/tokens.css frontend/src/styles/index.css
```

Resolve material findings in the same batch; document advisory-only findings without rerunning the detector.

- [ ] **Step 6: Commit verified corrections if needed**

```powershell
git add frontend/src
git commit -m "fix: refine scientific console responsiveness"
```

---

### Task 4: Refresh public evidence and complete repository gates

**Files:**
- Modify: `reports/public/woundscope-ui-showcase.webp`
- Modify: `PROGRESS.md` (ignored local evidence; do not stage)

**Interfaces:**
- Consumes: verified showcase mode.
- Produces: artifact-free public screenshot and fresh completion evidence.

- [ ] **Step 1: Capture and audit the public screenshot**

Capture the 1440×900 light-theme showcase as `reports/public/woundscope-ui-showcase.webp`. Verify RGB, one frame, 0 EXIF, and absence of medical images／masks, filenames, paths, tokens, model artifacts, personal data, browser chrome, fake predictions, and debug overlays.

- [ ] **Step 2: Run full frontend and Python gates**

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend test:run
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\audit_repository_privacy.py --repository .
git diff --check
```

Expected: every command exits 0; only pre-existing ONNX exporter warnings are acceptable.

- [ ] **Step 3: Update local progress evidence**

Record exact test counts, build results, viewport evidence, screenshot dimensions／privacy, detector result, branch, commits, and unchanged scientific／publication boundaries in `PROGRESS.md`. Do not stage it.

- [ ] **Step 4: Audit staged scope and commit**

```powershell
git diff --check
git status --short
git add reports/public/woundscope-ui-showcase.webp
git diff --cached --check
git commit -m "docs: refresh scientific console preview"
```

- [ ] **Step 5: Final identity and inventory audit**

```powershell
git status --short --branch
git log main..HEAD --format="%H%n%an <%ae>%n%cn <%ce>%n%B"
git diff --name-only main...HEAD
git ls-files | Select-String -Pattern '\.(onnx|pt|pth|safetensors|png|jpg|jpeg)$'
```

Expected: owner identity only, no co-author trailers, no tracked private/model artifact, and only the approved public WebP screenshot among new raster evidence.

- [ ] **Step 6: Preserve the visible preview**

Reload `http://127.0.0.1:7863/`, reset any temporary viewport override, show the browser, and retain the final tab for user review. Do not push, create a PR, tag, deploy, or publish model artifacts.
