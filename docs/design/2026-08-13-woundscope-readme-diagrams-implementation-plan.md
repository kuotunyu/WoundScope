# WoundScope README Diagrams Implementation Plan

> **For Codex:** Execute this plan inline with the repository-local `woundscope-development` workflow. Keep all scientific claims and the v0.2.2 code-only boundary unchanged.

**Goal:** Reorganize the README around a 60-second project narrative and add three GitHub-native Mermaid diagrams that make the system boundary, reproducible research workflow, and local review interaction immediately understandable.

**Architecture:** Documentation-only change. Mermaid remains embedded in `README.md`; no generated diagram artifact, runtime component, model file, API behavior, metric, or release metadata changes. Diagrams use conservative GitHub-compatible `flowchart` and `sequenceDiagram` syntax, explicit text labels, and GitHub theme-adaptive high-contrast colors; WoundScope styling is retained through typography, hierarchy, borders, screenshot, and prose.

**Tech Stack:** Markdown, Mermaid, Mermaid CLI, existing repository validation scripts, Python test suite, Ruff.

---

## Global constraints

- Work only in the canonical checkout on the active `codex/readme-diagram-readability` patch branch; do not create a clone or worktree.
- Do not add FUSeg images/masks, checkpoints, calibration artifacts, ONNX files, manifests, galleries, or secrets.
- Do not change scientific protocol, published metrics, model/API behavior, public claims, or release version.
- Preserve the distinction between public code/aggregate evidence and owner-provided private model artifacts.
- Do not imply patient-wise splitting, official-test evaluation, clinical diagnosis, severity, prognosis, or treatment advice.
- Keep zh-TW primary; retain technical proper nouns in their original form.
- No brittle prose unit test is required. Validation must exercise Mermaid parsing/rendering and existing README/repository contracts.

### Task 1: Draft and render-validate all three diagrams outside the README

**Files:**

- Reference: `README.md`
- Reference: `docs/design/2026-08-13-woundscope-readme-diagrams-design.md`
- Temporary only: Mermaid source and rendered preview files under the operating-system temp directory

- [x] Run the existing README/link/results validation baseline before changing `README.md`.
- [x] Confirm a Mermaid CLI is available; otherwise invoke a pinned `@mermaid-js/mermaid-cli` version without adding a repository dependency.
- [x] Draft the System Context + Architecture diagram with public, WoundScope, and private-artifact boundaries.
- [x] Draft the reproducible research workflow with the exact locked experimental stages and post-selection Official Validation boundary.
- [x] Draft the local review sequence with showcase/local-review branches, explicit submit, private runtime loading, sanitized response, and no-persistence behavior.
- [x] Parse and render each diagram to SVG/PNG; correct every Mermaid error before editing `README.md`.
- [x] Inspect rendered previews at desktop and narrow widths for label size, contrast, line crossings, and excessive horizontal spread.

### Task 2: Restructure the README and embed the validated diagrams

**Files:**

- Modify: `README.md`

- [x] Preserve the title, badges, value proposition, non-clinical warning, UI screenshot, verified metrics, quick start, limitations, and release links.
- [x] Replace the current generic architecture/pipeline section with a `60 秒看懂 WoundScope` section and the validated System Context + Architecture diagram.
- [x] Add a concise `可重現研究 Pipeline` section with the validated workflow diagram and explicit dev-selection/Official-Validation boundary notes.
- [x] Keep verified results immediately after the research workflow so evidence follows the method.
- [x] Add `本機複核如何運作` before Quick Start with the validated sequence diagram and short privacy/runtime notes.
- [x] Remove duplicated prose and unnecessary heading depth; keep paragraphs short and labels readable.
- [x] Audit every new sentence against the locked scientific and permission claims.

### Task 3: Verify the final README and record evidence

**Files:**

- Modify: `PROGRESS.md`
- Verify: `README.md`

- [x] Extract the final Mermaid blocks from `README.md` and render all three again with Mermaid CLI.
- [x] Inspect the final README structure and rendered diagrams at desktop and narrow widths.
- [x] Run README link checks, result-marker checks, release-metadata checks, privacy audit, Python tests, Ruff, formatter check, and `git diff --check` using the repository's current commands.
- [x] Confirm the diff contains documentation only and no prohibited artifacts or scientific/runtime changes.
- [x] Record exact PASS/FAIL commands and results in `PROGRESS.md` without changing the project milestone or release version.
- [x] Commit with `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` as the only author/committer.
- [x] Leave the branch local and ready for review; do not push until the user explicitly authorizes publication.

### Task 4: Apply the approved readability revision

**Files:**

- Modify: `README.md`
- Modify: `docs/design/2026-08-13-woundscope-readme-diagrams-design.md`
- Modify: `docs/design/2026-08-13-woundscope-readme-diagrams-implementation-plan.md`
- Modify: `PROGRESS.md` (local, ignored evidence only)
- Temporary only: extracted Mermaid source and default／dark render previews under the operating-system temp directory

- [ ] Render the current three diagrams and verify the reported failure at 823px GitHub content width: 18px base text plus excessive width／lifelines produces projected text below the 16px readability target.
- [ ] Replace Diagram 1 with a single-user entry model; fold FUSeg into the research-pipeline description instead of treating it as a peer role.
- [ ] Translate diagram labels to zh-TW where natural while retaining GitHub Repository、Public Colab、React、FastAPI、ONNX Runtime、Official Validation、Bootstrap and other proper nouns.
- [ ] Raise all three Mermaid base font sizes to 22px and shorten node／edge labels so the effective rendered size remains at least 16px at 823px width.
- [ ] Reduce the sequence diagram to four lifelines and the local-review happy path; remove autonumber and keep showcase behavior in prose.
- [ ] Extract the final Mermaid blocks and render all three under default and dark themes; inspect every PNG and record viewBox／projected font metrics.
- [ ] Run README／release regressions, Ruff, format, full pytest, privacy audit, frontend gates and `git diff --check`; record evidence in `PROGRESS.md`.
- [ ] Commit with owner-only identity. Keep publication external actions separate from local verification.
