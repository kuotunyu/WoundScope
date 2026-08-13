# WoundScope Intuitive Usage Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add concise, mode-aware guidance so a GitHub visitor understands how to enable WoundScope locally and a local-review user understands the explicit upload-to-review flow.

**Architecture:** Add one stateless `WorkflowGuide` presentation component with `showcase` and `review` variants, then compose it into the existing `ResearchShowcase` and `ReviewWorkspace`. Preserve all API/session behavior and express hierarchy through the current Scientific Console typography and dividers rather than new cards or modal state.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, axe-core, CSS custom properties, FastAPI, Python 3.12.

## Global Constraints

- Work only in the canonical checkout on `codex/ui-review-workbench`; do not create a clone or worktree.
- Human-readable copy is zh-TW-first; technical proper nouns remain in English.
- The public mode remains code-only and must not display a disabled upload, fake prediction, synthetic medical case, model download, or public-inference promise.
- The showcase CTA text is exactly `查看本機啟用方式` and targets `https://github.com/kuotunyu/WoundScope#啟動分割複核工作台`.
- Local review keeps explicit submission: selecting a file must never call inference until `開始分割複核` is pressed.
- Workflow text is at least 16px; interactive targets are at least 44px.
- Do not add full borders, surface cards, shadows, or large radii to individual steps.
- Preserve verified metrics, provenance facts, confidence semantics, medical warnings, API schema, session behavior, and `PERMISSION_PENDING`.
- Do not add or track medical images, masks, weights, ONNX, filenames, private paths, galleries, secrets, or image-level artifacts.
- Do not merge, deploy, train, or publish model artifacts. Do not push without explicit user authorization.
- Git author and committer remain `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` without trailers.

---

## File Structure

```text
frontend/src/components/WorkflowGuide.tsx
  Stateless semantic ordered-list component for showcase/review guidance.

frontend/src/components/ResearchShowcase.tsx
  Owns the code-only explanation, setup guide placement, and existing research links.

frontend/src/features/review/ReviewWorkspace.tsx
  Places the operation guide before the existing upload console; inference behavior remains unchanged.

frontend/src/app/App.test.tsx
  Covers public-mode capability language, setup CTA, semantic ordered list, and absence of fake controls.

frontend/src/features/review/ReviewWorkspace.test.tsx
  Covers local-review guidance while retaining explicit-submit behavior.

frontend/src/styles/index.css
  Provides divider-based desktop/mobile layout, typography, and CTA states.

design-system/woundscope/MASTER.md
  Records the mode-aware guidance pattern and prohibition on misleading disabled controls.

reports/public/woundscope-ui-showcase.webp
  Privacy-safe 1440×900 public preview refreshed after browser verification.

PROGRESS.md
  Records exact local test/browser/privacy evidence; follow the repository's existing tracking policy.
```

### Task 1: Lock the mode-aware semantic contract

**Files:**
- Modify: `frontend/src/app/App.test.tsx`
- Modify: `frontend/src/features/review/ReviewWorkspace.test.tsx`
- Create: `frontend/src/components/WorkflowGuide.tsx`
- Modify: `frontend/src/components/ResearchShowcase.tsx`
- Modify: `frontend/src/features/review/ReviewWorkspace.tsx`

**Interfaces:**
- Consumes: `variant: "showcase" | "review"`.
- Produces: `WorkflowGuide({ variant }: WorkflowGuideProps): JSX.Element`, a named region with one ordered list; showcase additionally produces one README CTA.

- [ ] **Step 1: Write failing showcase tests**

Add this test to `frontend/src/app/App.test.tsx`:

```tsx
it("explains how to move from code-only showcase to local review", async () => {
  mockStatus();
  render(<App />);
  await screen.findByText("研究展示模式");

  const guide = screen.getByRole("region", { name: "使用流程" });
  expect(within(guide).getByRole("list")).toBeVisible();
  expect(within(guide).getByText("準備 artifacts")).toBeVisible();
  expect(within(guide).getByText("啟動本機工作台")).toBeVisible();
  expect(within(guide).getByText("上傳並複核")).toBeVisible();
  expect(within(guide).getByRole("link", { name: "查看本機啟用方式" })).toHaveAttribute(
    "href",
    "https://github.com/kuotunyu/WoundScope#啟動分割複核工作台",
  );
  expect(screen.queryByLabelText("選擇傷口影像")).not.toBeInTheDocument();
  expect(screen.queryByText("立即推論")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Write the failing local-review test**

Replace the obsolete `expect(screen.queryByText("01")).not.toBeInTheDocument()` assertion in `frontend/src/features/review/ReviewWorkspace.test.tsx` with:

```tsx
const guide = screen.getByRole("region", { name: "操作流程" });
expect(guide).toBeVisible();
expect(within(guide).getByText("選擇影像")).toBeVisible();
expect(within(guide).getByText("明確開始分割")).toBeVisible();
expect(within(guide).getByText("比較並人工複核")).toBeVisible();
expect(within(guide).queryByRole("link")).not.toBeInTheDocument();
```

Also add `within` to the Testing Library import.

- [ ] **Step 3: Run both focused tests and verify RED**

Run:

```powershell
pnpm --dir frontend test:run -- src/app/App.test.tsx src/features/review/ReviewWorkspace.test.tsx
```

Expected: showcase fails because `使用流程` is absent; local review fails because `操作流程` is absent.

- [ ] **Step 4: Create the minimal semantic component**

Create `frontend/src/components/WorkflowGuide.tsx` with this structure:

```tsx
import { ArrowRight } from "lucide-react";

interface WorkflowGuideProps {
  variant: "showcase" | "review";
}

const guideContent = {
  showcase: {
    title: "使用流程",
    steps: [
      ["準備 artifacts", "在自己的機器準備 private ONNX 與 calibration metadata。"],
      ["啟動本機工作台", "設定環境變數並啟動本機 FastAPI。"],
      ["上傳並複核", "執行 segmentation、比較圖層，再由專業人員人工確認。"],
    ],
  },
  review: {
    title: "操作流程",
    steps: [
      ["選擇影像", "PNG、JPEG 或 WebP；選取後只建立本機預覽。"],
      ["明確開始分割", "按下主要按鈕後，影像才會傳給本機 API。"],
      ["比較並人工複核", "檢視 Original、Overlay、Mask、confidence 與 review reasons。"],
    ],
  },
} as const;

export function WorkflowGuide({ variant }: WorkflowGuideProps) {
  const content = guideContent[variant];
  const titleId = `workflow-guide-${variant}`;

  return (
    <section className={`workflow-guide workflow-guide-${variant}`} aria-labelledby={titleId}>
      <div className="workflow-guide-heading">
        <h2 id={titleId}>{content.title}</h2>
        {variant === "showcase" ? <span>Local review path</span> : <span>3 steps</span>}
      </div>
      <ol className="workflow-steps">
        {content.steps.map(([title, description], index) => (
          <li key={title}>
            <span className="workflow-index" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <strong>{title}</strong>
              <p>{description}</p>
            </div>
          </li>
        ))}
      </ol>
      {variant === "showcase" ? (
        <a
          className="setup-link"
          href="https://github.com/kuotunyu/WoundScope#啟動分割複核工作台"
        >
          查看本機啟用方式
          <ArrowRight size={18} aria-hidden="true" />
        </a>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 5: Compose both variants without changing behavior**

Import `WorkflowGuide` into `ResearchShowcase.tsx` and place `<WorkflowGuide variant="showcase" />` after `.mode-status` and before `.showcase-links`.

Import it into `ReviewWorkspace.tsx` and place `<WorkflowGuide variant="review" />` after `.workspace-intro` and before `.upload-console`.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
pnpm --dir frontend test:run -- src/app/App.test.tsx src/features/review/ReviewWorkspace.test.tsx
```

Expected: both files pass; existing explicit-submit assertion still proves `predictSpy` is not called on file selection.

- [ ] **Step 7: Commit the semantic feature**

```powershell
git add frontend/src/app/App.test.tsx frontend/src/features/review/ReviewWorkspace.test.tsx frontend/src/components/WorkflowGuide.tsx frontend/src/components/ResearchShowcase.tsx frontend/src/features/review/ReviewWorkspace.tsx
git commit -m "feat: add mode-aware usage guidance"
```

### Task 2: Integrate the Scientific Console visual pattern

**Files:**
- Modify: `frontend/src/styles/index.css`
- Modify: `design-system/woundscope/MASTER.md`

**Interfaces:**
- Consumes: `.workflow-guide`, `.workflow-guide-showcase`, `.workflow-guide-review`, `.workflow-guide-heading`, `.workflow-steps`, `.workflow-index`, and `.setup-link`.
- Produces: a three-column divider layout on desktop, compact vertical flow on narrow screens, 16px minimum guidance text, and a 44px setup CTA.

- [ ] **Step 1: Add the desktop visual contract**

Add the following bounded CSS near `.mode-status` and `.showcase-links`:

```css
.workflow-guide {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.workflow-guide-showcase {
  margin-top: 14px;
}

.workflow-guide-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
}

.workflow-guide-heading h2 {
  margin: 0;
  font-family: var(--font-sans);
  font-size: 18px;
  font-weight: 700;
}

.workflow-guide-heading span {
  color: var(--muted-ink);
  font-family: ui-monospace, "Cascadia Mono", monospace;
  font-size: 16px;
}

.workflow-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 0;
  padding: 0;
  list-style: none;
}

.workflow-steps li {
  display: grid;
  min-width: 0;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  padding-right: 10px;
}

.workflow-steps li + li {
  padding-left: 10px;
  border-left: 1px solid var(--border);
}

.workflow-index {
  color: var(--accent);
  font-family: ui-monospace, "Cascadia Mono", monospace;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.workflow-steps strong {
  display: block;
  font-size: 16px;
  line-height: 1.35;
}

.workflow-steps p {
  margin: 3px 0 0;
  color: var(--muted-ink);
  font-size: 16px;
  line-height: 1.45;
}

.setup-link {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 0 15px;
  border: 1px solid var(--primary);
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--surface);
  font-weight: 700;
  text-decoration: none;
}

.setup-link:hover {
  filter: brightness(0.94);
}

.workflow-guide-review {
  display: grid;
  grid-template-columns: minmax(160px, 0.7fr) minmax(0, 4fr);
  gap: 20px;
}

.workflow-guide-review .workflow-guide-heading {
  display: block;
  margin: 0;
}
```

During the browser pass, adjust only spacing and line lengths required to keep the left showcase aligned with the 390px research plate and retain visible evidence at 1440×900. Do not reduce any visible text below 16px.

- [ ] **Step 2: Add narrow-layout behavior**

Inside `@media (max-width: 820px)`, make `.workflow-guide-review` one column. Inside `@media (max-width: 520px)`, make `.workflow-steps` one column and replace column borders with top dividers:

```css
.workflow-guide-review {
  grid-template-columns: 1fr;
  gap: 8px;
}

.workflow-steps {
  grid-template-columns: 1fr;
}

.workflow-steps li,
.workflow-steps li + li {
  padding: 8px 0;
  border-left: 0;
}

.workflow-steps li + li {
  border-top: 1px solid var(--border);
}
```

- [ ] **Step 3: Update the design-system rule**

Add a concise `Mode-aware guidance` rule to `design-system/woundscope/MASTER.md`: use one semantic ordered list, `showcase` setup CTA, and `review` operation flow; never imply model availability with disabled upload or fake prediction.

- [ ] **Step 4: Run frontend verification**

```powershell
pnpm --dir frontend test:run
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Expected: all commands exit 0 with no warnings treated as errors.

- [ ] **Step 5: Commit the visual integration**

```powershell
git add frontend/src/styles/index.css design-system/woundscope/MASTER.md
git commit -m "refactor: clarify workbench usage flow"
```

### Task 3: Verify the rendered workflow and repository boundaries

**Files:**
- Modify if a reproduced visual defect requires it: `frontend/src/styles/index.css`
- Modify: `reports/public/woundscope-ui-showcase.webp`
- Modify according to repository tracking policy: `PROGRESS.md`

**Interfaces:**
- Consumes: the production Vite bundle served by the existing FastAPI process at `http://127.0.0.1:7863/`.
- Produces: verified responsive showcase guidance, a privacy-safe public screenshot, and exact gate evidence.

- [ ] **Step 1: Reload and inspect the production bundle**

After `pnpm --dir frontend build`, reload `http://127.0.0.1:7863/` without setting model environment variables. Inspect 1440×900, 1024×768, and 390×844 in light and dark themes for:

- the three showcase steps and setup CTA;
- immediate understanding that the current mode is code-only;
- no disabled upload or fake prediction;
- no horizontal overflow, clipping, console warning, or console error;
- 16px minimum guidance copy and 44px CTA;
- verified evidence remains visible or begins within the first 1440×900 viewport;
- no extra card, shadow, or rounded container around individual steps.

- [ ] **Step 2: Apply one bounded correction batch if needed**

Only change `frontend/src/styles/index.css` for defects reproduced in Step 1. Rebuild and repeat only affected viewport checks once.

- [ ] **Step 3: Capture and privacy-audit the public preview**

Capture the final 1440×900 light showcase as `reports/public/woundscope-ui-showcase.webp`. Verify RGB, one frame, no EXIF, and no medical image, mask, prediction, private filename/path, token, model artifact, browser chrome, or debug overlay.

- [ ] **Step 4: Run the full repository gate**

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

Expected: every command exits 0; only the two documented legacy ONNX exporter deprecation warnings are acceptable.

- [ ] **Step 5: Record evidence and commit the verified preview**

Update `PROGRESS.md` with exact test counts, build result, browser viewports, screenshot metadata, privacy result, unchanged permission state, branch, and commits. Stage it only if the current repository tracking policy includes it.

```powershell
git add reports/public/woundscope-ui-showcase.webp
git add -u PROGRESS.md
git diff --cached --check
git commit -m "docs: refresh guided workbench preview"
```

- [ ] **Step 6: Audit final scope and identity**

```powershell
git status --short --branch
git log -4 --format="%H %an <%ae> %cn <%ce> %s"
git diff origin/codex/ui-review-workbench...HEAD --stat
```

Confirm only UI guidance, design documentation, privacy-safe preview, and progress evidence changed; no data, weights, ONNX, metrics, scientific claims, or permission state changed.
