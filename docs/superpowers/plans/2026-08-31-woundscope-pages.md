# WoundScope Static GitHub Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-reviewable, zero-runtime-JavaScript, zh-TW-first static research showcase whose aggregate evidence is projected from pinned `v0.2.2` Git objects, without deploying or changing any GitHub／HF setting.

**Architecture:** A stdlib-only Python projector reads immutable Git objects, validates the approved README table and exact aggregate SVG, escapes dynamic text, and renders a nine-file publish tree into ignored temporary storage. A separate auditor constructs the acyclic SBOM → manifest → review-receipt integrity chain and rejects every file or claim outside the public boundary; an isolated Playwright／axe reviewer package tests the finished tree without becoming a production dependency.

**Tech Stack:** CPython 3.11.15 and 3.12.13, Python stdlib plus existing pytest／Ruff dev tools, HTML5／CSS, SPDX 2.3 JSON, Node.js 24.16.0, pnpm 11.16.0, `@playwright/test` 1.62.1, `axe-core` 4.13.0, GitHub Actions pinned by 40-character SHA.

## Global Constraints

- Implementation base remains descended from remote-main lock `b6f23032d0d55e7442b43724cb059ba67198d3c8`; stop if a fresh `git fetch origin` shows `origin/main` elsewhere.
- Evidence is the annotated `v0.2.2` tag object `1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4`, peeled commit `1b3df3b516cc4d366dc9da3cb01e8d0a319be613`, README blob `f5b8dd4681738aa372072cac9c827478d13c1f68`, DATA_CARD blob `2b7fe52ac9784c9c2682300d2bd56bb72b20d19c`, MODEL_CARD blob `c93a99579ad1b4fb1d03b0a6e15ba8300287ca9c`, and SVG blob `28d91ba5f6fb61d1114106e7519007d6aeb5d6b8`.
- The SVG is exactly 3,059 bytes with SHA-256 `e2e8d211a33ac62942fac64eceae23def21a32c53b51039fe2c504421793b89c`; it is copied from the evidence Git blob, never the worktree path.
- Production has 0 JavaScript, 0 WebAssembly, 0 raster, 0 upload／API／inference／model-download code, 0 remote assets, and 0 external runtime request. Test-only axe injection is never written to `publish/`.
- Public copy is zh-TW-first, aggregate-only, research-only, non-official-test, and non-clinical. It never claims accuracy percentage, diagnosis, severity, treatment, triage, external／multi-center validation, or patient-wise evidence.
- The only external anchors are the nine exact URLs in `site/links.allowlist.json`; they require `target="_blank" rel="noopener noreferrer"`. Colab and Hugging Face are absent.
- The production base path is exactly `/WoundScope/`; `404.html` has no path／query reflection or JavaScript.
- Generated outputs live only under ignored `temp/` or fresh OS temporary directories. Do not add or commit a publish tree, screenshot, receipt, browser binary, trace, cache, or clinical/scientific private artifact.
- Never open or traverse `.env*`, ignored `data/**`, `artifacts/**`, checkpoints, weights, image-level results, patient data, or private deployment artifacts. Task 0 may read and update only the three explicitly authorized private local-control files.
- Do not import, copy, or bundle `frontend/src/app/App.tsx`, `frontend/src/features/review/**`, `frontend/src/lib/api/**`, `app/**`, model runtime, Docker, Gradio, FastAPI, HF candidate, data, weight, or ONNX files.
- Do not enable Pages, add a deployment workflow, change About／homepage／visibility／topics, push, publish, open a PR, or operate HF. The workflow in this plan is read-only and non-deploying.
- Every commit has author and committer `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` and no co-author trailer. Stage only named paths; `git add .`, `git add -A`, wildcard staging, and force-adding ignored governance files are forbidden.
- Browser review supply chain is exact: Node 24.16.0; pnpm 11.16.0; `@playwright/test` 1.62.1 (`sha512-DTcUc8qii+cpHvtOwggMtBRMjKZHXYWdw8syRYu2vtzuq4Wxphqq4NfCs5Zt44L6mA8rfDfj+PHnxFc/FeK6mQ==`); `playwright` 1.62.1 (`sha512-0M+L3LAD8/nm554LOla9Ayx0j0tmFZ0FBcoQ7F1VuVHpM/XpiC8RcDzBQB8W5+hA8L22THxELzeF+2WcUzvcLg==`); `playwright-core` 1.62.1 (`sha512-wPYSwEBJY9GHraISXqyqtx0na0LpO3XEX7jNDhntbex7tzUS7kLnZsOlFruFJB4Hi/rhDMjXGqHewDZ68nYZVw==`); `axe-core` 4.13.0 (`sha512-UzGt8zg7Ny8djbYMhxl2zuEevVa7r2gJjYY5Lwr1xM7+XU2nd6CkIWFTVcCIbAP63vSz71NaVyyuSk9lHKcy0A==`); optional `fsevents` 2.3.2 (`sha512-xiqMQR4xAeHTuB9uWm+fFRcIOgKBMiOBP+eXiyT7jsgVCq1bkVygt00oASowB7EdtpOHaaPgKt812P9ab+DDKA==`).
- Browser revisions are Chromium 1234 (`151.0.7922.34`), Firefox 1538 (`153.0`), and WebKit 2336 (`26.5`). A mismatch in installed `playwright-core/browsers.json` fails before a page opens.
- Every pnpm dependency installation first runs the stdlib package-policy audit, then uses the committed exact lockfile with both `--frozen-lockfile` and `--ignore-scripts`. `package.json` has no lifecycle hook, no production dependency, and no script／dependency outside the approved exact maps. Browser acquisition is a later explicit `playwright install` phase, never an install lifecycle side effect.
- Controlled package／browser acquisition may use its explicitly approved registries before review execution. The later browser no-egress gate means loopback-only application server plus pre-navigation request ledger／abort; it does not claim a host firewall, air gap, or whole-host offline isolation.
- Publish byte budgets are blocking: `.nojekyll` = 0; `index.html` ≤ 65,536; `404.html` ≤ 8,192; CSS ≤ 32,768; aggregate SVG = 3,059; `LICENSE.txt` = 11,782; `THIRD_PARTY_NOTICES.txt` ≤ 16,384; `sbom.spdx.json` ≤ 65,536; `pages-manifest.json` ≤ 32,768; all nine files together ≤ 237,568 bytes.
- Browser gates cover Chromium／Firefox／WebKit × 375×667, 390×844, 768×1024, 1024×768, 1440×900 × light／dark; keyboard, focus, contrast, 200% reflow, no-egress, subpath, and 404 checks are mandatory.

---

## File and Responsibility Map

**Committed production-source boundary**

- Create `site/index.template.html`: fixed semantic page shell and approved zh-TW copy; no metric literals.
- Create `site/404.template.html`: fixed safe 404 shell.
- Create `site/site.css`: minimal authored styling, light／dark／high-contrast／responsive rules; no remote URL or import.
- Create `site/links.allowlist.json`: the nine exact user-initiated external navigation URLs.
- Create `site/THIRD_PARTY_NOTICES.txt`: deterministic project／aggregate-evidence attribution and explicit “no bundled third-party runtime package” statement.

**Committed stdlib build-review tooling**

- Create `scripts/pages_site/__init__.py`: package marker and public exports only.
- Create `scripts/pages_site/constants.py`: immutable Git locks, public allowlists, CSP, budgets, and schema versions.
- Create `scripts/pages_site/evidence.py`: typed Git-object reader and README evidence parser.
- Create `scripts/pages_site/svg_contract.py`: exact-byte, safe-XML, accessibility, and metric-consistency verifier.
- Create `scripts/pages_site/render.py`: escaped HTML／CSS／NOTICE renderer.
- Create `scripts/pages_site/integrity.py`: file hashes, SPDX, manifest, tree digest, review receipt, export, and central-seal validation.
- Create `scripts/build_pages_site.py`: clean-commit CLI orchestrator.
- Create `scripts/audit_pages_site.py`: `verify`, `compare`, `seal-review`, and `record-central-seal` CLI.

**Committed Python tests**

- Create `tests/pages/test_evidence.py`: annotated-tag／blob／README parser contracts.
- Create `tests/pages/test_svg_contract.py`: exact SVG and hostile-XML rejection.
- Create `tests/pages/test_render.py`: HTML escaping, claims, links, CSP, semantic table, zero-JS source.
- Create `tests/pages/test_integrity.py`: no-cycle SBOM／manifest／receipt and deterministic tree digest.
- Create `tests/pages/test_audit_cli.py`: nine-file allowlist, budgets, privacy, tamper, and CLI failure behavior.

**Committed isolated browser-review tooling**

- Create `site-review/package.json` and `site-review/pnpm-lock.yaml`: exact reviewer-only dependencies.
- Create `site-review/playwright.config.mjs`: three engines and review-only output paths.
- Create `site-review/check-toolchain.mjs`: exact package integrity／browser revision receipt.
- Create `site-review/test-server.mjs`: loopback-only Pages-subpath and safe 404 server.
- Create `site-review/pages.spec.mjs`: five-viewports × two-color-schemes, keyboard, axe, zoom, no-egress, CSP, and artifact checks.
- Create `scripts/verify_pages_review_package.py`: pre-install stdlib audit of exact package／lockfile policy and lifecycle-script absence.
- Create `tests/pages/test_reviewer_package_policy.py`: hostile package／lock mutation tests that run before dependency acquisition.

**Committed CI review only**

- Create `.github/workflows/pages-review.yml`: read-only build／test／artifact workflow with no deployment permission.

**Never committed**

- The three ignored local-control files updated by Task 0.
- `temp/pages-review/**`, `review-receipt.json`, `CENTRAL_SEAL.json`, screenshots, request／axe reports, Playwright results, generated publish files, browser downloads, and caches.

---

### Task 0: Safe Local Governance Sync and UTF-8 Baseline

**Files:**
- Modify locally, never stage: primary-checkout `AGENTS.md`
- Modify locally, never stage: primary-checkout `PROJECT_PLAN.md`
- Modify locally, never stage: primary-checkout `PROGRESS.md`
- Inspect only: `.gitignore`, `pyproject.toml`, `uv.lock`, `frontend/package.json`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: approved D-drive Git common directory and the already authorized isolated worktree.
- Produces: synchronized local-control state, clean implementation worktree, and reproducible Python 3.11／3.12 baseline evidence. It produces no public commit.

- [ ] **Step 1: Revalidate exact checkout, remote lock, worktree cleanliness, and private-path exclusions**

Run from the authorized implementation worktree in PowerShell:

```powershell
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$sourceRoot = (git rev-parse --show-toplevel).Trim()
if ((git status --porcelain=v1 -uno)) { throw 'Tracked worktree must be clean.' }
git fetch origin
$originMain = (git rev-parse origin/main).Trim()
if ($originMain -ne 'b6f23032d0d55e7442b43724cb059ba67198d3c8') { throw "origin/main drifted to $originMain; stop for central review." }
git merge-base --is-ancestor b6f23032d0d55e7442b43724cb059ba67198d3c8 HEAD
if ($LASTEXITCODE -ne 0) { throw 'Implementation HEAD is not descended from the approved base.' }
$tagType = (git cat-file -t 1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4).Trim()
$peeled = (git rev-parse '1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4^{}').Trim()
if ($tagType -ne 'tag' -or $peeled -ne '1b3df3b516cc4d366dc9da3cb01e8d0a319be613') { throw 'Evidence tag lock failed.' }
@('.env', '.env.local', 'artifacts', 'checkpoints') | ForEach-Object {
  if (Test-Path -LiteralPath $_) { Write-Host "PRIVATE_PATH_PRESENT_NOT_READ $_" }
}
```

Expected: fetch is read-only; all assertions pass; paths are only existence-checked and never opened.

- [ ] **Step 2: Locate the primary checkout without a machine-local hardcoded path**

```powershell
$worktreeRecords = @(git worktree list --porcelain)
$primaryLine = $worktreeRecords | Where-Object { $_ -like 'worktree *' } | Select-Object -First 1
if (-not $primaryLine) { throw 'Primary worktree not found.' }
$primaryRoot = $primaryLine.Substring('worktree '.Length)
$sourceCommon = (git rev-parse --path-format=absolute --git-common-dir).Trim()
$primaryCommon = (git -C $primaryRoot rev-parse --path-format=absolute --git-common-dir).Trim()
if ($sourceCommon -ne $primaryCommon) { throw 'Primary and source worktrees do not share a Git common directory.' }
@('AGENTS.md', 'PROJECT_PLAN.md', 'PROGRESS.md') | ForEach-Object {
  if (-not (Test-Path -LiteralPath (Join-Path $primaryRoot $_))) { throw "Missing authorized local-control file: $_" }
  $ignored = (git -C $primaryRoot check-ignore -- $_).Trim()
  if ($ignored -ne $_) { throw "Local-control file is not ignored: $_" }
}
```

Expected: all three authorized files exist only in the primary local-control checkout and are ignored.

- [ ] **Step 3: Update only the authorized local-control records**

Use `apply_patch` against the three files under `$primaryRoot`; do not enumerate or read other ignored files. Preserve their existing format and add these exact decisions:

```text
AGENTS.md
- Canonical checkout discovery: use `git rev-parse --show-toplevel` inside the centrally approved D-drive checkout; the obsolete absolute C-drive path is not authoritative.
- Current public release: v0.2.2; annotated tag object 1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4; peeled evidence commit 1b3df3b516cc4d366dc9da3cb01e8d0a319be613.
- Website decision: static GitHub Pages research showcase only; no upload, API, inference, model download, HF runtime, deploy permission, Pages activation, or About change in this implementation phase.

PROJECT_PLAN.md Decision Log — 2026-08-31
- Approved a zero-runtime-JavaScript, zh-TW-first, aggregate-only static Pages review artifact.
- Site source and v0.2.2 evidence provenance remain separate.
- Implementation ends at local/read-only CI review and central seal; deployment is a later independent gate.

PROGRESS.md — 2026-08-31 Pages implementation gate
- Worktree/branch: derive from `git worktree list` and `git branch --show-current`; do not store a machine-local absolute path.
- Base lock: b6f23032d0d55e7442b43724cb059ba67198d3c8.
- Evidence lock: tag object 1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4; peeled commit 1b3df3b516cc4d366dc9da3cb01e8d0a319be613.
- Gate: local-only/read-only CI artifact; no push, deployment, Pages activation, About edit, or HF operation.
```

After editing:

```powershell
@('AGENTS.md', 'PROJECT_PLAN.md', 'PROGRESS.md') | ForEach-Object {
  git -C $primaryRoot check-ignore -v -- $_
}
if ((git -C $sourceRoot status --porcelain=v1 -uno)) { throw 'Governance sync contaminated source worktree.' }
```

Expected: the files remain ignored and no source-worktree change is created. Do not commit this step.

- [ ] **Step 4: Establish isolated UTF-8 Python 3.11.15 baseline**

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py311'
uv sync --frozen --extra dev --python 3.11.15
uv run --python 3.11.15 python -c "import sys; assert sys.version_info[:3] == (3, 11, 15); assert sys.flags.utf8_mode == 1"
uv run --python 3.11.15 pytest -q tests/test_repository_privacy.py tests/test_readme_results.py tests/test_release_metadata.py
```

Expected: all selected public-index／release tests pass without downloading data, weights, models, browser binaries, or app／train extras. The repository privacy test reads tracked Git index blobs, not ignored worktree files.

- [ ] **Step 5: Establish isolated UTF-8 Python 3.12.13 baseline**

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py312'
uv sync --frozen --extra dev --python 3.12.13
uv run --python 3.12.13 python -c "import sys; assert sys.version_info[:3] == (3, 12, 13); assert sys.flags.utf8_mode == 1"
uv run --python 3.12.13 pytest -q tests/test_repository_privacy.py tests/test_readme_results.py tests/test_release_metadata.py
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

Expected: the same selected baseline passes. Do not use the known invalid system Anaconda Python 3.10 environment.

- [ ] **Step 6: Record the Task 0 checkpoint without a commit**

```powershell
git status --short
git diff --name-only
```

Expected: no tracked change. Reviewer explicitly confirms that only the three authorized ignored local-control files were touched and no `.env`, data, model, image, or private artifact was opened.

---

### Task 1: Immutable Git Evidence Model and README Parser

**Files:**
- Create: `scripts/pages_site/__init__.py`
- Create: `scripts/pages_site/constants.py`
- Create: `scripts/pages_site/evidence.py`
- Create: `tests/pages/test_evidence.py`

**Interfaces:**
- Consumes: repository root `Path` and the fixed tag／blob constants.
- Produces: `PublicEvidence`, `EvidenceRow`, `EvidenceProvenance`; `read_git_object(repository: Path, object_id: str, expected_type: str) -> bytes`; `load_public_evidence(repository: Path) -> PublicEvidence`.

- [ ] **Step 1: Write failing annotated-tag and parser tests**

Create `tests/pages/test_evidence.py` with tests that:

```python
from pathlib import Path

import pytest

from scripts.pages_site.evidence import EvidenceContractError, load_public_evidence, parse_results_table


REPOSITORY = Path(__file__).resolve().parents[2]


def test_loads_exact_release_objects_and_two_models() -> None:
    evidence = load_public_evidence(REPOSITORY)
    assert evidence.provenance.tag_name == "v0.2.2"
    assert evidence.provenance.tag_object == "1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4"
    assert evidence.provenance.peeled_commit == "1b3df3b516cc4d366dc9da3cb01e8d0a319be613"
    assert [row.model_id for row in evidence.rows] == ["unet_efficientnet_b0", "segformer_b0"]
    assert all(row.loss == "bce_dice" and row.seeds == (42, 43, 44) for row in evidence.rows)


def test_rejects_duplicate_result_markers() -> None:
    readme = load_public_evidence(REPOSITORY).readme_bytes
    with pytest.raises(EvidenceContractError, match="RESULT_MARKER_COUNT"):
        parse_results_table(readme + b"\n<!-- RESULTS_TABLE_START -->\n")
```

Also assert exact README／DATA_CARD／MODEL_CARD blob IDs, exactly eight table columns, finite `Decimal` numeric values, unique model IDs, and one marker pair. Do not type metric values into test source; obtain all numeric values from the pinned blob.

- [ ] **Step 2: Run RED test**

```powershell
$env:PYTHONUTF8 = '1'
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py312'
uv run --python 3.12.13 pytest -q tests/pages/test_evidence.py
```

Expected: FAIL during import because `scripts.pages_site.evidence` does not exist.

- [ ] **Step 3: Implement constants and typed evidence parsing**

In `constants.py`, define the full 40-character locks, expected tagger `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`, marker bytes, expected column names, expected model IDs, loss, and seeds. In `evidence.py`, use only `subprocess.run([...], shell=False, cwd=repository, check=True, capture_output=True)` and parse numeric cells with `decimal.Decimal`; reject `NaN`／Infinity, Unicode decode errors, duplicate markers, missing pipes, extra rows, and extra columns.

Use these exact immutable types:

```python
@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    tag_name: str
    tag_object: str
    peeled_commit: str
    readme_blob: str
    data_card_blob: str
    model_card_blob: str
    svg_blob: str


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    model_id: str
    loss: str
    seeds: tuple[int, int, int]
    dice_mean: Decimal
    dice_sd: Decimal
    dice_ci_low: Decimal
    dice_ci_high: Decimal
    iou_mean: Decimal
    iou_sd: Decimal
    precision_mean: Decimal
    precision_sd: Decimal
    recall_mean: Decimal
    recall_sd: Decimal
    specificity_mean: Decimal
    specificity_sd: Decimal


@dataclass(frozen=True, slots=True)
class PublicEvidence:
    provenance: EvidenceProvenance
    rows: tuple[EvidenceRow, EvidenceRow]
    validation_images: int
    bootstrap_iterations: int
    readme_bytes: bytes
```

Git verification order is type `tag` → tag payload／tagger／name → peeled commit → path blob IDs → README bytes → marker and schema parse. Raise `EvidenceContractError(code, public_path=None)` with stable codes and never echo blob contents or machine paths.

- [ ] **Step 4: Run GREEN parser and style gates**

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_evidence.py
uv run --python 3.12.13 ruff check scripts/pages_site tests/pages/test_evidence.py
uv run --python 3.12.13 ruff format --check scripts/pages_site tests/pages/test_evidence.py
```

Expected: PASS on all three commands.

- [ ] **Step 5: Commit only the evidence unit**

```powershell
git add -- scripts/pages_site/__init__.py scripts/pages_site/constants.py scripts/pages_site/evidence.py tests/pages/test_evidence.py
$staged = @(git diff --cached --name-only)
$expected = @('scripts/pages_site/__init__.py','scripts/pages_site/constants.py','scripts/pages_site/evidence.py','tests/pages/test_evidence.py')
if (@(Compare-Object $expected $staged).Count) { throw 'Unexpected staged path.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'feat: lock Pages evidence projection'
```

Expected: one owner-only commit and clean tracked status.

---

### Task 2: Exact Aggregate SVG Verifier

**Files:**
- Modify: `scripts/pages_site/constants.py`
- Create: `scripts/pages_site/svg_contract.py`
- Create: `tests/pages/test_svg_contract.py`

**Interfaces:**
- Consumes: `PublicEvidence` and exact SVG Git-blob bytes.
- Produces: `VerifiedSvg(bytes_value: bytes, sha256: str, git_blob: str, public_filename: str)`; `SvgContractError`; `verify_svg_bytes(svg_bytes: bytes, evidence: PublicEvidence, enforce_exact_bytes: bool = True) -> VerifiedSvg`; `load_verified_svg(repository: Path, evidence: PublicEvidence) -> VerifiedSvg`.

- [ ] **Step 1: Write failing exact-byte, accessibility, and hostile-XML tests**

```python
def test_exact_svg_matches_evidence_without_worktree_read() -> None:
    evidence = load_public_evidence(REPOSITORY)
    verified = load_verified_svg(REPOSITORY, evidence)
    assert len(verified.bytes_value) == 3059
    assert verified.sha256 == "e2e8d211a33ac62942fac64eceae23def21a32c53b51039fe2c504421793b89c"
    assert verified.public_filename == "model-comparison-e2e8d211a33ac629.svg"


@pytest.mark.parametrize("needle,replacement,code", [
    (b'role="img"', b'role="presentation"', "SVG_ROLE"),
    (b"</svg>", b'<script>0</script></svg>', "SVG_ELEMENT"),
    (b"</svg>", b'<image href="https://example.invalid/x"/></svg>', "SVG_ELEMENT"),
])
def test_rejects_mutated_svg(needle: bytes, replacement: bytes, code: str) -> None:
    evidence = load_public_evidence(REPOSITORY)
    source = read_git_object(REPOSITORY, evidence.provenance.svg_blob, "blob")
    with pytest.raises(SvgContractError, match=code):
        verify_svg_bytes(source.replace(needle, replacement), evidence, enforce_exact_bytes=False)
```

Also test missing／duplicate `title` and `desc`, DOCTYPE／entity, `style`, `foreignObject`, `use`, event attributes, `href`, `url(`, `data:`, remote fonts, and a visible Dice／IoU token changed in memory. The changed expected numeric value must be derived from `PublicEvidence`, not typed into test source.

- [ ] **Step 2: Run RED test**

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_svg_contract.py
```

Expected: FAIL because the SVG verifier module is missing.

- [ ] **Step 3: Implement exact safe-SVG verification**

Use `xml.etree.ElementTree.fromstring` only after rejecting `<!DOCTYPE` and `<!ENTITY` case-insensitively. Accept only namespace-qualified `svg`, `title`, `desc`, `rect`, `text`, `g`, and `line`; maintain explicit per-element attribute allowlists, reject every attribute whose local name begins with `on`, and reject any value containing `url(`, `data:`, `http:`, or `https:`.

Verify byte length, lowercase SHA-256, Git blob ID, root `role="img"`, exact `aria-labelledby="title desc"`, unique non-empty accessible names, model display names, seeds note, official-validation note, non-clinical caveat, and Dice／IoU values formatted from the parsed `Decimal` rows. Never normalize or reserialize approved SVG bytes.

- [ ] **Step 4: Run GREEN and cross-version gates**

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_evidence.py tests/pages/test_svg_contract.py
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py311'
uv run --python 3.11.15 pytest -q tests/pages/test_evidence.py tests/pages/test_svg_contract.py
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py312'
uv run --python 3.12.13 ruff check scripts/pages_site tests/pages
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

Expected: both Python versions pass; Ruff passes.

- [ ] **Step 5: Commit only the SVG contract**

```powershell
git add -- scripts/pages_site/constants.py scripts/pages_site/svg_contract.py tests/pages/test_svg_contract.py
$staged = @(git diff --cached --name-only)
$expected = @('scripts/pages_site/constants.py','scripts/pages_site/svg_contract.py','tests/pages/test_svg_contract.py')
if (@(Compare-Object $expected $staged).Count) { throw 'Unexpected staged path.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'feat: verify approved Pages SVG evidence'
```

---

### Task 3: Escaped Zero-JavaScript Static Renderer

**Files:**
- Create: `site/index.template.html`
- Create: `site/404.template.html`
- Create: `site/site.css`
- Create: `site/links.allowlist.json`
- Create: `site/THIRD_PARTY_NOTICES.txt`
- Create: `scripts/pages_site/render.py`
- Create: `tests/pages/test_render.py`

**Interfaces:**
- Consumes: `PublicEvidence`, `VerifiedSvg`, a full `site_source_sha`, authored templates, CSS, NOTICE, and the exact link allowlist.
- Produces: `escape_text(value: str) -> str`; `RenderedSite(index_html: bytes, not_found_html: bytes, css: bytes, notices: bytes)` through `render_site(evidence: PublicEvidence, verified_svg: VerifiedSvg, site_source_sha: str, site_root: Path) -> RenderedSite`; all dynamic strings pass through `html.escape(value, quote=True)`.

- [ ] **Step 1: Write failing render-boundary tests**

Tests must define `collect_anchors(document: bytes) -> list[Anchor]` in the same file using a small `html.parser.HTMLParser` subclass whose immutable `Anchor` record has `href: str`, `target: str | None`, and `rel: set[str]`, then assert:

```python
def test_renderer_escapes_dynamic_values_and_separates_provenance() -> None:
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    rendered = render_site(
        evidence=evidence,
        verified_svg=verified_svg,
        site_source_sha="a" * 40,
        site_root=REPOSITORY / "site",
    )
    text = rendered.index_html.decode("utf-8")
    assert escape_text("<script>") == "&lt;script&gt;"
    assert "Site source" in text and "Evidence source" in text
    assert text.index("<table") < text.index("model-comparison-")
    assert "script-src 'none'" in text
    assert "<script" not in text.casefold()


def test_only_exact_external_links_are_emitted() -> None:
    evidence = load_public_evidence(REPOSITORY)
    verified_svg = load_verified_svg(REPOSITORY, evidence)
    document = render_site(evidence, verified_svg, "a" * 40, REPOSITORY / "site").index_html
    anchors = collect_anchors(document)
    allowlist = json.loads((REPOSITORY / "site/links.allowlist.json").read_text("utf-8"))
    external = [anchor for anchor in anchors if anchor.href.startswith("https://")]
    assert {anchor.href for anchor in external} == set(allowlist)
    assert all(anchor.target == "_blank" and anchor.rel == {"noopener", "noreferrer"} for anchor in external)
```

Also assert one H1; no skipped heading; skip link first; table caption／`scope` headers; no form, input, button, contenteditable, download, iframe, video, audio, source, preload, prefetch, preconnect, canonical remote fetch, inline style, JS event handler, root `/assets/`, Colab, HF, medical-device or forbidden clinical phrases. Scan `site/**` for metric tokens derived dynamically from `PublicEvidence`; expect zero matches.

- [ ] **Step 2: Run RED test**

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_render.py
```

Expected: FAIL because render source and templates do not exist.

- [ ] **Step 3: Author the exact external-navigation allowlist**

Write `site/links.allowlist.json` as sorted UTF-8／LF JSON containing exactly:

```json
[
  "https://doi.org/10.1038/s41598-020-78799-w",
  "https://github.com/kuotunyu/WoundScope",
  "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/CITATION.cff",
  "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/DATA_CARD.md",
  "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/LICENSE",
  "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/MODEL_CARD.md",
  "https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/README.md",
  "https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.2",
  "https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge"
]
```

Builder validation compares normalized URLs byte-for-byte to this set and rejects fragments, query parameters, redirects, shorteners, `mailto:`, `data:`, and `javascript:`.

- [ ] **Step 4: Author semantic templates and approved claim ceiling**

`index.template.html` contains `<html lang="zh-Hant-TW">`, viewport, description, candidate canonical URL, exact meta CSP, skip link, one H1, header／nav／main／section／figure／table／footer, and only named `{{SLOT_NAME}}` tokens. Dynamic metric rows are not present in source.

The visible copy must include these exact boundaries without hiding them in `<details>`:

```text
WoundScope
足部潰瘍二元語意分割的靜態研究成果展示
研究用途 · 非 official-test · 非臨床效能
本頁只展示方法、可重現控制與鎖定 Official Validation 的彙總結果；不提供影像上傳、API、推論、模型或醫療建議。
彙總證據
結果來自單一公開資料來源的 200 張 Official Validation；每個架構使用 seeds 42／43／44。Dice 95% CI 為 2,000 次 image-level percentile Bootstrap；因沒有 patient ID，無法校正同一病患多張影像的相關性。
這些是 observed research results，不是 official-test、外部、多中心或臨床表現，也不能推論診斷、治療、安全性或跨機構優勢。
Site source
Evidence source
公開邊界：code、methodology、aggregate evidence；不公開資料影像、weights、ONNX、image-level results 或 live model。
```

The overview includes a fixed inline decorative abstract contour `<svg aria-hidden="true" focusable="false">` made only of simple authored paths／circles; it has no raster, wound-like texture, medical imagery, external reference, label, or evidence role. The approved aggregate SVG remains a same-origin `<img>` after the full semantic table.

`404.template.html` uses the same CSP and CSS, says `找不到此頁面`, and links only to `/WoundScope/`; it never interpolates a request path or query.

- [ ] **Step 5: Author minimal responsive CSS and NOTICE**

CSS uses system stacks only, no `@import`, `url(`, font bytes, animation dependency, or external token. It defines visible `:focus-visible`, skip-link reveal, 44×44 px link targets, a single-column narrow layout, a bounded `.table-scroll` region, `color-scheme: light dark`, `@media (prefers-color-scheme: dark)`, `@media (prefers-contrast: more)`, `@media (forced-colors: active)`, and `@media (prefers-reduced-motion: reduce)`. At ≤640 CSS px, page body never scrolls horizontally.

`site/THIRD_PARTY_NOTICES.txt` is deterministic and contains:

```text
WoundScope Static Research Showcase — Third-Party Notices

Bundled third-party runtime packages: none.
The production site contains authored HTML/CSS, WoundScope project material under Apache-2.0, and a WoundScope-authored aggregate SVG projected from the pinned v0.2.2 Git evidence object.

Aggregate research-fact attribution (not bundled software or redistributed data):
FUSeg / Foot Ulcer Segmentation Challenge, pinned public source revision 42a272dfe0679f20675e826385925cb7562934b6.
Publication: https://doi.org/10.1038/s41598-020-78799-w
Source: https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge

No FUSeg image, mask, patient/sample identifier, model weight, ONNX artifact, or image-level result is redistributed by this site. Apache-2.0 does not assert ownership of FUSeg or model artifacts.

Build/review-only tools are reported separately in the review artifact and are not production runtime components.
```

- [ ] **Step 6: Implement escaped rendering and run GREEN tests**

`render.py` reads only the five committed `site/` files, rejects unknown／missing／duplicate template slots, calls `html.escape(..., quote=True)` for every scalar from Git evidence or provenance, and generates table rows cell-by-cell. It serializes UTF-8 without BOM and LF line endings. Fixed trusted template markup is never populated from Markdown or raw evidence HTML.

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_evidence.py tests/pages/test_svg_contract.py tests/pages/test_render.py
uv run --python 3.12.13 ruff check scripts/pages_site tests/pages
uv run --python 3.12.13 ruff format --check scripts/pages_site tests/pages
```

Expected: PASS; source metric scan returns zero and link allowlist count is nine.

- [ ] **Step 7: Commit only static source and renderer**

```powershell
git add -- site/index.template.html site/404.template.html site/site.css site/links.allowlist.json site/THIRD_PARTY_NOTICES.txt scripts/pages_site/render.py tests/pages/test_render.py
$staged = @(git diff --cached --name-only)
$expected = @('scripts/pages_site/render.py','site/404.template.html','site/THIRD_PARTY_NOTICES.txt','site/index.template.html','site/links.allowlist.json','site/site.css','tests/pages/test_render.py')
if (@(Compare-Object $expected $staged).Count) { throw 'Unexpected staged path.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'feat: render zero-JavaScript Pages source'
```

This is committed source only. Do not generate or stage a publish directory before the commit; generated output must identify a real, non-self-referential source commit.

---

### Task 4: Deterministic Builder, Auditor, SPDX, Manifest, Receipt, and Budgets

**Files:**
- Modify: `scripts/pages_site/constants.py`
- Create: `scripts/pages_site/integrity.py`
- Create: `scripts/build_pages_site.py`
- Create: `scripts/audit_pages_site.py`
- Create: `tests/pages/test_integrity.py`
- Create: `tests/pages/test_audit_cli.py`

**Interfaces:**
- Consumes: clean repository commit, rendered source, exact evidence objects, output directories under `temp/` or OS temp, optional review reports.
- Produces: immutable `BuildResult(publish: Path, site_source_sha: str, manifest_sha256: str, sbom_sha256: str, publish_tree_sha256: str)` and `VerifiedPublish` with the same five fields; `PagesAuditError`; `build_site(repository: Path, output: Path, site_source_sha: str, source_date_epoch: int) -> BuildResult`; `verify_publish_tree(publish: Path) -> VerifiedPublish`; `compare_publish_trees(left: Path, right: Path) -> None`; `seal_review(publish: Path, reports: Path, export_root: Path) -> Path`; `record_central_seal(receipt: Path, output: Path, approved_site_source: str, reviewer: str, approval_id: str) -> Path`.

- [ ] **Step 1: Write failing no-cycle and deterministic digest tests**

Tests build into two `tmp_path` directories through the pure Python interface and assert:

```python
def build_for_test(output: Path) -> BuildResult:
    repository = Path(__file__).resolve().parents[2]
    site_source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_date_epoch = int(subprocess.run(
        ["git", "show", "-s", "--format=%ct", site_source_sha],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip())
    return build_site(repository, output, site_source_sha, source_date_epoch)


def test_integrity_graph_is_acyclic_and_exact(tmp_path: Path) -> None:
    first = build_for_test(tmp_path / "one")
    manifest = json.loads((first.publish / "pages-manifest.json").read_text("utf-8"))
    sbom = json.loads((first.publish / "sbom.spdx.json").read_text("utf-8"))
    manifest_paths = {item["path"] for item in manifest["files"]}
    sbom_paths = {item["fileName"].removeprefix("./") for item in sbom["files"]}
    assert "pages-manifest.json" not in manifest_paths
    assert "sbom.spdx.json" in manifest_paths
    assert "pages-manifest.json" not in sbom_paths
    assert "sbom.spdx.json" not in sbom_paths
    assert len(manifest_paths) == 8
    assert len(sbom_paths) == 7


def test_two_clean_builds_are_byte_identical(tmp_path: Path) -> None:
    left = build_for_test(tmp_path / "left")
    right = build_for_test(tmp_path / "right")
    compare_publish_trees(left.publish, right.publish)
    assert left.publish_tree_sha256 == right.publish_tree_sha256
```

Also test that manifest records SBOM hash／bytes, tree digest uses the same eight non-manifest files, receipt is outside publish and records manifest／SBOM／tree digests, and a receipt or manifest never records its own hash.

- [ ] **Step 2: Write failing allowlist, privacy, and budget tests**

`tests/pages/test_audit_cli.py` mutates a copied temp publish tree and expects stable public error codes for: extra file, missing file, symlink, non-regular mode, `.js`, `.wasm`, raster, source map, absolute home path, secret-like token, data／artifact name, metric drift, external link, CSP change, wrong subpath, CSS `url(`, oversized HTML, SBOM self-file, manifest self-file, bad tree digest, unsafe SPDX license, and tampered LICENSE.

```python
@pytest.mark.parametrize("relative_name,code", [
    ("extra.txt", "TREE_EXTRA_FILE"),
    ("assets/runtime.js", "TREE_JAVASCRIPT"),
    ("assets/example.webp", "TREE_RASTER"),
    ("data/rows.csv", "TREE_PRIVATE_DATA"),
])
def test_publish_tree_fails_closed_on_extra_content(
    audited_publish: Path, relative_name: str, code: str
) -> None:
    target = audited_publish / relative_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    with pytest.raises(PagesAuditError, match=code):
        verify_publish_tree(audited_publish)
```

- [ ] **Step 3: Run RED tests**

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_integrity.py tests/pages/test_audit_cli.py
```

Expected: FAIL because integrity and CLI modules do not exist.

- [ ] **Step 4: Implement the ordered, non-self-referential builder**

The build uses a private staging directory and promotes output only after every gate passes. It executes this exact order:

1. Resolve and validate the full `site_source_sha`; get `SOURCE_DATE_EPOCH` from `%ct` of that commit.
2. Read templates, CSS, links, NOTICE, and site-source `LICENSE` through Git objects at `site_source_sha`, not from a dirty worktree. Require LICENSE blob `6d7d4eed049964731c06b000d257a1bdb2fd6028`, 11,782 bytes, SHA-256 `46f4aa5b30f1e3fdec3c30ff381da83fe0323a00d8d7bde8f1a16265c1305fd1` unless a later central review explicitly changes this lock.
3. Load evidence and exact SVG from the pinned evidence commit.
4. Normalize authored CSS bytes first, compute its SHA-256, and choose `site-` plus the first 16 lowercase hex characters as its filename. Then render `index.html`／`404.html` with that exact asset name and write `.nojekyll`, `LICENSE.txt`, `THIRD_PARTY_NOTICES.txt`, hashed CSS, and exact SVG. The SVG filename is fixed by its approved bytes.
5. Generate SPDX 2.3 `sbom.spdx.json` with deterministic namespace／creation time, one WoundScope production package, seven file records for every publish file except SBOM and manifest, SHA-256 checksums, concluded／declared Apache-2.0 for WoundScope-authored files, and no browser／Python build-tool package as runtime.
6. Hash the resulting eight non-manifest files. Build `publish_tree_sha256` from records sorted by POSIX-path UTF-8 bytes, each encoded `path NUL decimal_bytes NUL lowercase_sha256 LF`.
7. Generate `pages-manifest.json` listing exactly those eight files including SBOM, plus dual provenance, base path, tool versions, claim/network schema, and tree digest. Do not add manifest hash／bytes to itself.
8. Audit the final nine-file staging tree; atomically rename staging to the requested empty output directory. On failure, leave no deployable output.

All JSON is `json.dumps(..., ensure_ascii=False, sort_keys=True, indent=2) + "\n"`; all text is UTF-8 without BOM and LF. No build timestamp other than source commit time, random ID, absolute path, username, runner name, or environment dump enters publish bytes.

- [ ] **Step 5: Implement exact publish verification and review sealing**

`verify_publish_tree` accepts exactly:

```text
.nojekyll
index.html
404.html
LICENSE.txt
THIRD_PARTY_NOTICES.txt
sbom.spdx.json
pages-manifest.json
assets/site-[0-9a-f]{16}.css
assets/model-comparison-e2e8d211a33ac629.svg
```

It uses `Path.lstat`, rejects links／devices, enforces per-file and 237,568-byte total budgets, recomputes the seven-file SPDX view, eight-file manifest view, and eight-file tree digest, and verifies claims／CSP／links／subpath／zero-JS／privacy. Browser runtime verification is deliberately absent; HTML says no client-side cryptographic verification.

`seal_review` first verifies publish and a strict report allowlist (`toolchain.json`, `network.json`, `axe.json`, `keyboard.json`, `contrast.json`, `zoom.json`, `browser-summary.json`, and `screenshots/**/*.png`). Final sealing requires `zoom.json.manual_browser_zoom_200_percent` to contain PASS records for all three exact browser revisions; automated content-reflow emulation is a separate field and cannot satisfy it. It copies publish into `export_root/publish`, copies only allowed reports into `export_root/reports`, and writes `export_root/review-receipt.json`. The receipt records site/evidence identities, manifest SHA-256, SBOM SHA-256, publish tree digest, report hashes, and a `review_payload_sha256` over `publish/` plus `reports/`; it excludes itself and `CENTRAL_SEAL.json`.

`record_central_seal` runs only after explicit central approval. It verifies clean HEAD equals the receipt site source, writes `CENTRAL_SEAL.json` beside—not inside—the export, and records receipt SHA-256, site/evidence identities, reviewer `kuotunyu`, explicit approval ID, and decision `approved`. It never changes GitHub or deploys.

- [ ] **Step 6: Implement PowerShell-safe CLIs**

```text
python scripts/build_pages_site.py --repository . --output <empty-directory> --site-source HEAD
python scripts/audit_pages_site.py verify --publish <publish-directory>
python scripts/audit_pages_site.py compare --left <first-publish> --right <second-publish>
python scripts/audit_pages_site.py seal-review --publish <publish> --reports <reports> --output <empty-export-directory>
python scripts/audit_pages_site.py record-central-seal --receipt <review-receipt.json> --output <new-seal-path> --approved-site-source <40-hex> --reviewer kuotunyu --approval-id <central-issued-id>
```

Use `argparse` `Path` values and subprocess argument arrays; never shell-concatenate paths. Error output contains only stable code and safe relative public path. `record-central-seal` refuses missing central-issued ID, a pre-existing output, dirty tracked state, or mismatched HEAD.

- [ ] **Step 7: Run GREEN unit, tamper, formatting, and privacy gates**

```powershell
uv run --python 3.12.13 pytest -q tests/pages
uv run --python 3.12.13 ruff check scripts/pages_site scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages
uv run --python 3.12.13 ruff format --check scripts/pages_site scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages
uv run --python 3.12.13 python scripts/audit_repository_privacy.py --repository .
```

Expected: all page tests pass, Ruff passes, and tracked-index privacy status is `ok`. The privacy command reads public Git index blobs only and never ignored worktree data.

- [ ] **Step 8: Commit source before generating the real artifact**

```powershell
git add -- scripts/pages_site/constants.py scripts/pages_site/integrity.py scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages/test_integrity.py tests/pages/test_audit_cli.py
$staged = @(git diff --cached --name-only)
$expected = @('scripts/audit_pages_site.py','scripts/build_pages_site.py','scripts/pages_site/constants.py','scripts/pages_site/integrity.py','tests/pages/test_audit_cli.py','tests/pages/test_integrity.py')
if (@(Compare-Object $expected $staged).Count) { throw 'Unexpected staged path.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'feat: build and audit deterministic Pages tree'
```

- [ ] **Step 9: From the clean commit, generate two ignored builds and compare them**

```powershell
if ((git status --porcelain=v1 -uno)) { throw 'Tracked tree must be clean before source-bound build.' }
$siteSha = (git rev-parse HEAD).Trim()
$runRoot = Join-Path 'temp/pages-review' $siteSha
if (Test-Path -LiteralPath $runRoot) { throw 'Review run path already exists; choose a fresh worktree instead of overwriting evidence.' }
New-Item -ItemType Directory -Path (Join-Path $runRoot 'first') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $runRoot 'second') -Force | Out-Null
uv run --python 3.12.13 python scripts/build_pages_site.py --repository . --output (Join-Path $runRoot 'first/publish') --site-source $siteSha
uv run --python 3.12.13 python scripts/build_pages_site.py --repository . --output (Join-Path $runRoot 'second/publish') --site-source $siteSha
uv run --python 3.12.13 python scripts/audit_pages_site.py verify --publish (Join-Path $runRoot 'first/publish')
uv run --python 3.12.13 python scripts/audit_pages_site.py compare --left (Join-Path $runRoot 'first/publish') --right (Join-Path $runRoot 'second/publish')
git check-ignore -v -- $runRoot
git status --short
```

Expected: byte-identical nine-file trees, exact source SHA in UI／manifest, evidence SHA separate, ignored output, and clean tracked status.

---

### Task 5: Pinned Three-Engine Browser, Accessibility, Responsive, and No-Egress Review

**Files:**
- Create: `site-review/package.json`
- Create: `site-review/pnpm-lock.yaml`
- Create: `site-review/playwright.config.mjs`
- Create: `site-review/check-toolchain.mjs`
- Create: `site-review/test-server.mjs`
- Create: `site-review/pages.spec.mjs`
- Create: `scripts/verify_pages_review_package.py`
- Create: `tests/pages/test_reviewer_package_policy.py`

**Interfaces:**
- Consumes: `WOUNDSCOPE_PAGES_PUBLISH_DIR`, `WOUNDSCOPE_PAGES_REPORT_DIR`, exact reviewer lockfile, loopback port 4173.
- Produces: `audit_review_package(package_path: Path, lockfile_path: Path) -> dict[str, object]` and its pre-install CLI; approved report allowlist plus PNG screenshots; exits nonzero on package policy, toolchain, browser, request, console, CSP, DOM, a11y, layout, keyboard, zoom, subpath, or 404 failure.

- [ ] **Step 1: Write the exact reviewer manifest／lockfile and failing pre-install policy tests**

`site-review/package.json` is authored with exactly eight top-level keys, is private, has no `dependencies`, requires Node `24.16.0`, declares `packageManager: "pnpm@11.16.0"`, and contains only these approved scripts and dev dependencies:

```json
{
  "name": "woundscope-pages-review",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "packageManager": "pnpm@11.16.0",
  "engines": {
    "node": "24.16.0"
  },
  "scripts": {
    "check:toolchain": "node check-toolchain.mjs",
    "test": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "1.62.1",
    "axe-core": "4.13.0"
  }
}
```

Author `pnpm-lock.yaml` together with this manifest from the centrally verified versions／integrities in Global Constraints; do not resolve or rewrite it through a non-frozen install. `tests/pages/test_reviewer_package_policy.py` imports `audit_review_package`, first validates the approved pair, then mutates copies in `tmp_path` to add `preinstall`, `install`, `postinstall`, `prepare`, an extra script, a production dependency, a ranged version, an extra package, or a changed integrity and requires a stable `ReviewerPackagePolicyError` code.

Run RED before dependency acquisition:

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_reviewer_package_policy.py
```

Expected: FAIL because `scripts/verify_pages_review_package.py` does not exist.

- [ ] **Step 2: Implement and run the observable pre-install contract**

The stdlib-only verifier parses JSON, treats the YAML lock as a constrained text contract, and requires: exact top-level manifest keys; the two exact scripts above; no lifecycle key of any casing; no `dependencies`, `optionalDependencies`, `peerDependencies`, `bundledDependencies`, or package-manager build allowlist; only the two exact dev dependencies; lockfile version 9; exact importer specifiers; the approved package closure and integrities; no patch, override, catalog, Git／file／workspace source, or unknown package. It prints deterministic JSON with manifest SHA-256, lockfile SHA-256, approved package closure, and `lifecycle_scripts: []` without executing Node or package code.

Run this observable policy gate before corepack or `pnpm install`, then perform the controlled package-acquisition phase with lifecycle execution disabled:

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_reviewer_package_policy.py
uv run --python 3.12.13 python scripts/verify_pages_review_package.py --package site-review/package.json --lockfile site-review/pnpm-lock.yaml
if ((node --version).Trim() -ne 'v24.16.0') { throw 'Node 24.16.0 required.' }
corepack enable
corepack prepare pnpm@11.16.0 --activate
if ((pnpm --version).Trim() -ne '11.16.0') { throw 'pnpm 11.16.0 activation failed.' }
pnpm -C site-review install --frozen-lockfile --ignore-scripts
```

Expected: policy tests and pre-install audit PASS; pnpm uses the exact committed lock, runs no lifecycle code, and installs package files only. No browser binary is acquired by this command.

- [ ] **Step 3: Implement the exact toolchain receipt**

`check-toolchain.mjs` reads `package.json`, `pnpm-lock.yaml` bytes, installed package metadata, and `playwright-core/browsers.json`. It rejects ranges and mismatches; expects Chromium 1234／151.0.7922.34, Firefox 1538／153.0, WebKit 2336／26.5; requires all three resolved Playwright executable paths to exist; and writes `toolchain.json` containing Node／pnpm versions, every resolved direct／transitive／optional package version／license／registry integrity, browser revisions／executable-presence booleans, and lockfile SHA-256. The expected package closure is `@playwright/test` 1.62.1, `playwright` 1.62.1, `playwright-core` 1.62.1, `axe-core` 4.13.0, plus platform-optional `fsevents` 2.3.2; any other resolved package or unknown license fails. It labels Playwright packages (Apache-2.0), axe-core (MPL-2.0), pnpm (MIT), and optional fsevents (MIT) as build-review-only, not production runtime.

Before explicit browser acquisition, perform syntax review only; the full checker is intentionally deferred because it must fail if browser executables are absent:

```powershell
node --check site-review/check-toolchain.mjs
```

Expected: syntax check passes without opening a browser or creating a report. Full integrity／executable validation occurs immediately after the separate browser-acquisition phase in Step 7.

- [ ] **Step 4: Implement loopback-only Pages-like test server**

`test-server.mjs` resolves the publish root from `WOUNDSCOPE_PAGES_PUBLISH_DIR`, rejects a missing／relative／non-directory path, binds only `127.0.0.1:4173`, serves `/WoundScope/` as `index.html`, serves exact allowlisted assets with safe MIME types, returns the bytes of `404.html` with status 404 for every unknown path, never redirects, never lists a directory, and never echoes request path／query in its body.

`playwright.config.mjs` sets `workers: 1`, `fullyParallel: false`, `retries: 0`, `trace: 'off'`, `video: 'off'`, `outputDir` below the ignored report root, and three exact projects using `chromium`, `firefox`, `webkit`. Its `webServer` starts only the local test server and waits for `/WoundScope/`.

- [ ] **Step 5: Write three-engine matrix and no-egress tests**

For every browser project, iterate the exact five viewport objects and `light`／`dark`. Register request and console listeners before navigation. A request is valid only when origin is `http://127.0.0.1:4173`, path starts `/WoundScope/`, and the normalized path maps to one of the nine manifest files; all external requests are aborted and fail the test.

Each matrix cell checks:

```javascript
expect(await page.locator('html').getAttribute('lang')).toBe('zh-Hant-TW');
expect(await page.locator('h1').count()).toBe(1);
expect(await page.locator('script').count()).toBe(0);
expect(await page.locator('form,input,button,iframe,video,audio').count()).toBe(0);
expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
expect(await page.locator('footer').isVisible()).toBe(true);
```

It also validates full site/evidence SHAs are distinct, table precedes aggregate image, external link attributes match the nine-item allowlist without clicking, CSS and SVG are same-origin, meta CSP is exact, no resource hint exists, and `performance.getEntriesByType('resource')` contains only expected same-origin files.

- [ ] **Step 6: Add keyboard, axe, contrast, zoom, subpath, and 404 gates**

- Keyboard: first Tab focuses the skip link; Enter moves focus to `main`; subsequent focus order contains links only; every focused link has visible outline and a bounding box at least 44×44 CSS px where the spec marks it touch-targeted.
- Axe: read exact local `axe-core/axe.min.js`, inject through Playwright evaluation after load, run WCAG 2.2 A／AA tags, and require zero serious／critical violations. This injected test code is not a network request or publish file.
- Contrast: axe color-contrast plus computed light／dark focus and non-text contrast; re-run with `forcedColors: 'active'` where the engine supports it and store exceptions as explicit unsupported capability, never a silent pass.
- Zoom: in all engines execute `document.documentElement.style.zoom = '2'`, then assert every visible landmark has a nonzero bounding box, body has no two-dimensional scroll, table scroller remains operable, footer is visible, and focus stays sequential. This is labeled automated 200% content-reflow emulation, not browser-chrome zoom. Final Task 7 separately requires an actual manual 200% browser-zoom receipt for all three engines.
- Subpath: request `/WoundScope/`, CSS, SVG, NOTICE, SBOM, manifest, direct reload, and unknown paths. Unknown path and unknown query both return status 404 with identical fixed body and no reflected string.
- Accessibility alternative: disable images and assert the complete results table／caption remains visible and understandable.

Write deterministic JSON summaries to the approved report filenames and PNG screenshots under `reports/screenshots/<engine>/<viewport>-<scheme>.png`. Do not commit snapshots, traces, videos, or reports.

- [ ] **Step 7: Separate controlled browser acquisition from RED→GREEN application no-egress execution**

Phase A is explicit browser acquisition. It may contact the Playwright browser distribution service and is not described as offline or as part of the application no-egress proof:

```powershell
pnpm -C site-review exec playwright install chromium firefox webkit
$siteSha = (git rev-parse HEAD).Trim()
$runRoot = Join-Path 'temp/pages-review' $siteSha
$env:WOUNDSCOPE_PAGES_REPORT_DIR = (Resolve-Path -LiteralPath $runRoot).Path + [IO.Path]::DirectorySeparatorChar + 'reports'
pnpm -C site-review check:toolchain
```

Phase B starts only after acquisition completes. It opens the loopback application under the request-ledger／abort contract; it does not claim whole-host offline isolation:

```powershell
$siteSha = (git rev-parse HEAD).Trim()
$runRoot = Join-Path 'temp/pages-review' $siteSha
$env:WOUNDSCOPE_PAGES_PUBLISH_DIR = (Resolve-Path -LiteralPath (Join-Path $runRoot 'first/publish')).Path
$env:WOUNDSCOPE_PAGES_REPORT_DIR = (Resolve-Path -LiteralPath $runRoot).Path + [IO.Path]::DirectorySeparatorChar + 'reports'
pnpm -C site-review test
```

Expected: initial run exposes any layout／accessibility defect. Add the focused failing assertion, fix only the owning `site/`／renderer source, and create a separate owner-only correction commit before rebuilding:

```powershell
git add -- site/index.template.html site/404.template.html site/site.css scripts/pages_site/render.py tests/pages/test_render.py
$staged = @(git diff --cached --name-only)
$allowed = @('site/index.template.html','site/404.template.html','site/site.css','scripts/pages_site/render.py','tests/pages/test_render.py')
if (-not $staged.Count -or @($staged | Where-Object { $_ -notin $allowed }).Count) { throw 'Unexpected correction staging.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'fix: harden Pages review contract'
```

Rebuild from the new clean commit and rerun until all three engines pass. Never weaken request, axe, contrast, or claim assertions to accept the defect. If no defect is found, do not create this correction commit.

- [ ] **Step 8: Commit only reviewer source, policy, tests, and exact lockfile**

Before committing, `pnpm-lock.yaml` must resolve `@playwright/test`, `playwright`, and `playwright-core` to 1.62.1 and axe-core to 4.13.0 with the Global Constraints integrities.

```powershell
git add -- site-review/package.json site-review/pnpm-lock.yaml site-review/playwright.config.mjs site-review/check-toolchain.mjs site-review/test-server.mjs site-review/pages.spec.mjs scripts/verify_pages_review_package.py tests/pages/test_reviewer_package_policy.py
$staged = @(git diff --cached --name-only)
$expected = @('scripts/verify_pages_review_package.py','site-review/check-toolchain.mjs','site-review/package.json','site-review/pages.spec.mjs','site-review/playwright.config.mjs','site-review/pnpm-lock.yaml','site-review/test-server.mjs','tests/pages/test_reviewer_package_policy.py')
if (@(Compare-Object $expected $staged).Count) { throw 'Unexpected staged path.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'test: add pinned Pages browser review'
```

After commit, make a fresh two-build run keyed by the new HEAD before rerunning browsers; old generated artifacts refer to the previous site source and are invalid.

---

### Task 6: Read-Only Non-Deploying CI Review Workflow

**Files:**
- Create: `.github/workflows/pages-review.yml`

**Interfaces:**
- Consumes: full Git history, exact Python／Node／pnpm locks, committed builder／review tests.
- Produces: short-lived `woundscope-pages-review-<site-sha>` artifact containing only `publish/`, `reports/`, and `review-receipt.json`; no deployment.

- [ ] **Step 1: Write a failing workflow contract test**

Extend `tests/pages/test_audit_cli.py` with a stdlib `tomllib`-free YAML text contract that checks exact immutable action SHAs, `permissions: contents: read`, `fetch-depth: 0`, no `pull_request_target`, no secret expression, no Pages action, no `pages: write`, no `id-token: write`, no environment, and no deploy job.

```python
def test_pages_review_workflow_is_read_only() -> None:
    text = (REPOSITORY / ".github/workflows/pages-review.yml").read_text("utf-8")
    assert "permissions:\n  contents: read" in text
    assert "fetch-depth: 0" in text
    policy = "python scripts/verify_pages_review_package.py --package site-review/package.json --lockfile site-review/pnpm-lock.yaml"
    install = "pnpm -C site-review install --frozen-lockfile --ignore-scripts"
    browser_acquire = "pnpm -C site-review exec playwright install --with-deps chromium firefox webkit"
    browser_execute = "pnpm -C site-review test"
    assert text.count(install) == 1
    assert text.index(policy) < text.index(install) < text.index(browser_acquire) < text.index(browser_execute)
    for forbidden in ("pull_request_target", "pages: write", "id-token: write", "deploy-pages", "configure-pages", "secrets."):
        assert forbidden not in text
```

Run:

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_audit_cli.py -k workflow
```

Expected: FAIL because the workflow is absent.

- [ ] **Step 2: Create exact read-only workflow**

Use triggers `pull_request`, `push`, and `workflow_dispatch`; top-level `permissions: contents: read`; concurrency cancellation; Ubuntu runner; and one review job. Pin:

```text
actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803
astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b
actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e
actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
```

Set checkout `fetch-depth: 0` and `fetch-tags: true`; Python 3.12.13; Node 24.16.0; corepack pnpm 11.16.0; `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, and `SOURCE_DATE_EPOCH` from checked-out commit. Do not use a secret or Pages permission.

The job executes in two visibly separated phases. Dependency and browser acquisition may use the approved package／Playwright distribution endpoints, but package lifecycle code remains disabled:

```text
uv sync --frozen --extra dev --python 3.12.13
uv run ruff check scripts/pages_site scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages
uv run ruff format --check scripts/pages_site scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages
uv run pytest -q tests/pages
uv run python scripts/audit_repository_privacy.py --repository .
uv run python scripts/build_pages_site.py --repository . --output temp/pages-review/first/publish --site-source "$GITHUB_SHA"
uv run python scripts/build_pages_site.py --repository . --output temp/pages-review/second/publish --site-source "$GITHUB_SHA"
uv run python scripts/audit_pages_site.py compare --left temp/pages-review/first/publish --right temp/pages-review/second/publish
uv run python scripts/verify_pages_review_package.py --package site-review/package.json --lockfile site-review/pnpm-lock.yaml
corepack enable && corepack prepare pnpm@11.16.0 --activate
pnpm -C site-review install --frozen-lockfile --ignore-scripts
pnpm -C site-review exec playwright install --with-deps chromium firefox webkit
pnpm -C site-review check:toolchain
```

Only after controlled acquisition succeeds does the application/browser execution phase start:

```text
pnpm -C site-review test
uv run python scripts/audit_pages_site.py seal-review --publish temp/pages-review/first/publish --reports temp/pages-review/reports --output temp/pages-review/export
```

The second phase enforces browser request-ledger／abort and a loopback-only server. It makes no whole-runner offline or host-firewall claim; acquisition requests are outside the application request ledger and are identified separately in the gate summary.

The artifact action uploads only `temp/pages-review/export`, uses an exact short retention, errors on missing files, and does not upload source, browser cache, Playwright package, or a second build tree. The workflow never calls an activation API.

- [ ] **Step 3: Run GREEN workflow and local-equivalent gates**

```powershell
uv run --python 3.12.13 pytest -q tests/pages/test_audit_cli.py -k workflow
rg -n "pages: write|id-token: write|deploy-pages|configure-pages|pull_request_target|secrets\." .github/workflows/pages-review.yml
```

Expected: pytest PASS and `rg` exits 1 with no matches. Then run the local-equivalent build／browser／seal commands without pushing; local success is sufficient for this gate.

- [ ] **Step 4: Commit only workflow and its focused test change**

```powershell
git add -- .github/workflows/pages-review.yml tests/pages/test_audit_cli.py
$staged = @(git diff --cached --name-only)
$expected = @('.github/workflows/pages-review.yml','tests/pages/test_audit_cli.py')
if (@(Compare-Object $expected $staged).Count) { throw 'Unexpected staged path.' }
git diff --cached --check
$env:GIT_AUTHOR_NAME = 'kuotunyu'; $env:GIT_AUTHOR_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
$env:GIT_COMMITTER_NAME = 'kuotunyu'; $env:GIT_COMMITTER_EMAIL = '61350295+kuotunyu@users.noreply.github.com'
git commit -m 'ci: add read-only Pages review gate'
```

Expected: no deployment file, setting, metadata change, or push.

---

### Task 7: Final Clean Export, Fresh-Eye Review, and Central Seal Gate

**Files:**
- Generate ignored: `temp/pages-review/<site-sha>-<run-id>/first/publish/**`
- Generate ignored: `temp/pages-review/<site-sha>-<run-id>/second/publish/**`
- Generate ignored: `temp/pages-review/<site-sha>-<run-id>/reports/**`
- Generate ignored: `temp/pages-review/<site-sha>-<run-id>/export/publish/**`
- Generate ignored: `temp/pages-review/<site-sha>-<run-id>/export/reports/**`
- Generate ignored: `temp/pages-review/<site-sha>-<run-id>/export/review-receipt.json`
- Generate only after approval, ignored: `temp/pages-review/<site-sha>-<run-id>/CENTRAL_SEAL.json`

**Interfaces:**
- Consumes: final clean local HEAD and all committed gates.
- Produces: locally reviewable export and a verifiable receipt. Central seal remains an explicit human approval action and does not deploy.

- [ ] **Step 1: Verify final source identity, exact commits, and clean tracked state**

```powershell
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if ((git status --porcelain=v1 -uno)) { throw 'Final source tree is dirty.' }
$siteSha = (git rev-parse HEAD).Trim()
git merge-base --is-ancestor b6f23032d0d55e7442b43724cb059ba67198d3c8 $siteSha
if ($LASTEXITCODE -ne 0) { throw 'Final source lost approved base ancestry.' }
git log --format='%H%x09%an <%ae>%x09%cn <%ce>%x09%B%x00' b6f23032d0d55e7442b43724cb059ba67198d3c8..HEAD |
  Select-String -Pattern 'Co-authored-by:|Co-Authored-By:' | ForEach-Object { throw 'Co-author trailer found.' }
$badIdentity = git log --format='%an <%ae>|%cn <%ce>' b6f23032d0d55e7442b43724cb059ba67198d3c8..HEAD |
  Where-Object { $_ -ne 'kuotunyu <61350295+kuotunyu@users.noreply.github.com>|kuotunyu <61350295+kuotunyu@users.noreply.github.com>' }
if ($badIdentity) { throw 'Non-owner commit identity found.' }
```

- [ ] **Step 2: Run final Python／privacy gates on both supported versions**

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py311'
uv run --python 3.11.15 pytest -q tests/pages
$env:UV_PROJECT_ENVIRONMENT = 'temp/pages-baseline/py312'
uv run --python 3.12.13 pytest -q tests/pages
uv run --python 3.12.13 ruff check scripts/pages_site scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages
uv run --python 3.12.13 ruff format --check scripts/pages_site scripts/build_pages_site.py scripts/audit_pages_site.py tests/pages
uv run --python 3.12.13 python scripts/audit_repository_privacy.py --repository .
Remove-Item Env:UV_PROJECT_ENVIRONMENT
```

Expected: every command passes; no actual model inference, model／data download, or private file read occurs.

- [ ] **Step 3: Build twice in fresh ignored directories**

```powershell
$runId = [Guid]::NewGuid().ToString('N')
$runRoot = Join-Path 'temp/pages-review' ($siteSha + '-' + $runId)
New-Item -ItemType Directory -Path (Join-Path $runRoot 'first') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $runRoot 'second') -Force | Out-Null
uv run --python 3.12.13 python scripts/build_pages_site.py --repository . --output (Join-Path $runRoot 'first/publish') --site-source $siteSha
uv run --python 3.12.13 python scripts/build_pages_site.py --repository . --output (Join-Path $runRoot 'second/publish') --site-source $siteSha
uv run --python 3.12.13 python scripts/audit_pages_site.py verify --publish (Join-Path $runRoot 'first/publish')
uv run --python 3.12.13 python scripts/audit_pages_site.py compare --left (Join-Path $runRoot 'first/publish') --right (Join-Path $runRoot 'second/publish')
```

Expected: exact inventory, budgets, no-cycle hashes, dual provenance, and byte determinism pass.

- [ ] **Step 4: Reuse prepared caches, fail closed, then run the browser execution phase**

Task 7 is not an acquisition phase. It requires pnpm 11.16.0, the exact package tarballs in the already prepared pnpm store, and all three exact Playwright browser revisions from Task 5／the controlled CI acquisition phase. Run the package-policy audit before pnpm; use offline＋frozen＋ignore-scripts; never retry without `--offline` and never call `playwright install` here:

```powershell
uv run --python 3.12.13 python scripts/verify_pages_review_package.py --package site-review/package.json --lockfile site-review/pnpm-lock.yaml
if ((pnpm --version).Trim() -ne '11.16.0') { throw 'PNPM_CACHE_NOT_PREPARED: return to the controlled acquisition phase.' }
pnpm -C site-review install --offline --frozen-lockfile --ignore-scripts
$env:WOUNDSCOPE_PAGES_PUBLISH_DIR = (Resolve-Path -LiteralPath (Join-Path $runRoot 'first/publish')).Path
$env:WOUNDSCOPE_PAGES_REPORT_DIR = (Resolve-Path -LiteralPath $runRoot).Path + [IO.Path]::DirectorySeparatorChar + 'reports'
New-Item -ItemType Directory -Path $env:WOUNDSCOPE_PAGES_REPORT_DIR -Force | Out-Null
pnpm -C site-review check:toolchain
pnpm -C site-review test
```

Expected: missing package cache, missing browser executable, revision mismatch, or integrity mismatch fails closed. The operator must return to the explicitly controlled acquisition phase and then restart Task 7 in a fresh run directory; Task 7 must not silently fall back to network. Once prerequisites exist, all three engines, five viewports, light／dark, keyboard, axe, contrast, content-reflow, request-ledger no-egress, subpath, and 404 checks pass. This does not assert whole-host offline isolation.

- [ ] **Step 5: Perform actual 200% browser-zoom and fresh-eye visual review**

This is a blocking **central manual gate**, not an unattended automation step. A central operator opens the loopback site in the exact three installed browser revisions in headed mode—or explicitly authorizes an available computer-use session—sets actual browser-chrome zoom to 200%, and inspects all five viewport sizes. If neither a central operator nor explicitly authorized headed computer-use is available, stop with `MANUAL_BROWSER_ZOOM_REQUIRED`; do not seal the review.

Record only pass/fail, browser revision, viewport, scheme, actual browser zoom, overflow, overlap, clipped text, table readability, focus visibility, footer visibility, and reviewer identity in `reports/zoom.json`／`browser-summary.json`; do not capture profiles, cookies, history, machine paths, or medical images. Automated `document.documentElement.style.zoom = '2'` results remain labeled `content_reflow_emulation` and can never populate or substitute the required `manual_browser_zoom_200_percent` field. `seal-review` must require that manual field to be present and PASS for all three engines.

Fresh-eye review must explicitly answer PASS for:

1. Nine-file publish allowlist is distinct from receipt／reports.
2. SBOM excludes SBOM＋manifest; manifest excludes manifest but hashes SBOM; receipt hashes manifest＋SBOM＋tree; no cycle exists.
3. UI, manifest, and receipt separate site source from evidence tag／commit; no self-attribution as scientific provenance.
4. External anchors are exactly nine, exclude Colab／HF, never auto-fetch, and have `noopener noreferrer`.
5. 404 uses exact CSP, fixed body, status 404, correct `/WoundScope/` return link, and no reflection.
6. NOTICE／SBOM classify Playwright／axe as review-only and contain no unsupported data／artifact license claim.
7. Review export contains `publish/`, `reports/`, receipt only; publish tree contains no screenshot／report／tool package.
8. Page never claims runtime digest checking; production contains zero JavaScript even though axe was injected during review.

- [ ] **Step 6: Seal a clean local review export**

```powershell
uv run --python 3.12.13 python scripts/audit_pages_site.py seal-review --publish (Join-Path $runRoot 'first/publish') --reports (Join-Path $runRoot 'reports') --output (Join-Path $runRoot 'export')
$receipt = Join-Path $runRoot 'export/review-receipt.json'
$receiptBytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $receipt))
$receiptSha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($receiptBytes)).ToLowerInvariant()
"site_source=$siteSha"
"review_receipt_sha256=$receiptSha256"
git check-ignore -v -- $runRoot
git status --short
```

Expected: export validates, receipt hash is available for central review, run root is ignored, and tracked status is clean. This local gate does not require a push or CI run.

- [ ] **Step 7: Stop at the central seal decision**

Report exact branch, worktree, base, final source commit, evidence tag object／peeled commit, publish tree digest, manifest SHA-256, SBOM SHA-256, receipt SHA-256, toolchain lockfile digest, browser revisions, test matrix results, byte budgets, and clean status. Provide the ignored local export for review. Do not run the next command until central gives an explicit approval ID bound to those exact digests.

After explicit approval only, central supplies `WOUNDSCOPE_CENTRAL_APPROVAL_ID` out of band:

```powershell
$approvalId = $env:WOUNDSCOPE_CENTRAL_APPROVAL_ID
if ([string]::IsNullOrWhiteSpace($approvalId) -or $approvalId -notmatch '^[A-Za-z0-9._-]+$') { throw 'Missing or invalid central approval ID.' }
uv run --python 3.12.13 python scripts/audit_pages_site.py record-central-seal --receipt $receipt --output (Join-Path $runRoot 'CENTRAL_SEAL.json') --approved-site-source $siteSha --reviewer kuotunyu --approval-id $approvalId
```

The seal remains ignored and local. It authorizes neither push nor deploy; Pages workflow／remote activation／About metadata／post-deploy smoke remain a separate future plan and central gate.

---

## Completion Evidence Required Before Handoff

- Task 0 private local-control sync completed without a public commit or app-source contamination.
- Exact source commits are owner-only, narrowly staged, descended from `b6f2303...`, and have no co-author trailer.
- Python 3.11.15 and 3.12.13 page tests pass in UTF-8 isolated environments; selected baseline and privacy audit pass without private-data access or real inference.
- Evidence tag, peeled commit, README／card／SVG blobs, SVG bytes／hash, README schema, metric-to-SVG consistency, and claim ceiling pass.
- The generated tree contains exactly nine files and respects every per-file／total byte budget.
- SBOM seven-file view, manifest eight-file view, tree digest eight-file view, and external receipt form the specified acyclic graph.
- Two fresh builds are byte-identical and source-bound to the final clean commit; generated output remains ignored and uncommitted.
- Reviewer lockfile integrities and Chromium 1234／Firefox 1538／WebKit 2336 revisions match; three engines × five viewports × light／dark plus keyboard／axe／contrast／zoom／no-egress／subpath／404 pass.
- Every pnpm install follows a passing pre-install manifest／lock policy audit and uses frozen lock＋ignore-scripts; controlled acquisition is separated from loopback request-ledger execution, and final cache-only install has no network fallback.
- The central manual 200% browser-chrome zoom gate passes in all three exact browsers; CSS content-reflow emulation is recorded separately and never substituted.
- Read-only CI workflow contains `contents: read` only and no Pages permission, deployment action, secret, privileged event, or activation.
- Final export contains only `publish/`, allowed `reports/`, and `review-receipt.json`; a central seal is created only after explicit digest-bound approval.
- No push, Pages activation, About edit, visibility／topics mutation, HF operation, model／data download, or real inference occurs.
