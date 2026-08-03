# WoundScope v0.1.0 Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a versioned, externally reproducible WoundScope `v0.1.0` release without publishing medical data, weights, ONNX binaries, private images, or image-level results.

**Architecture:** The full-run notebook keeps its verified private Drive ZIP path and adds a Public GitHub tag fallback that resolves to the same `project_dir`／`source_commit` interface. Release metadata, a privacy-safe aggregate SVG, GitHub security files, and CI hardening are independently testable repository layers. Publishing happens only after local, clean-checkout, privacy, contributor, and hosted CI gates pass.

**Tech Stack:** Python 3.10–3.12, pytest, JSON notebook cells, YAML/CFF/TOML metadata, SVG, GitHub Actions, GitHub CLI.

## Global Constraints

- Keep the locked FUSeg revision, `exclude_train` split policy, model families, losses, seeds, calibration, metrics, and official-validation role unchanged.
- Author and committer must remain `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` with no contributor trailers or bot-authored commits.
- Keep README, Release notes, Description, About, security copy, and issue forms primarily in `zh-TW`; preserve technical proper nouns in their original form.
- Do not track or publish `.env`, FUSeg images/masks, image-level manifests/results, galleries, checkpoints, ONNX binaries, sample predictions, or secrets.
- Do not run full local GPU training or invent new experiment values.
- Every behavior change follows RED → GREEN TDD and every release claim requires fresh verification evidence.

---

### Task 1: Public GitHub fallback for the full-run Colab notebook

**Files:**
- Modify: `tests/test_notebook_release.py`
- Modify: `notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb`

**Interfaces:**
- Consumes: optional `MyDrive/WoundScope/WoundScope_colab_source.zip`, optional `WOUNDSCOPE_GIT_URL`, optional `WOUNDSCOPE_GIT_REF`.
- Produces: `project_dir: pathlib.Path`, `source_commit: str`, `artifact_dir: pathlib.Path` for the unchanged install/CUDA/pipeline cells.

- [ ] **Step 1: Add failing source-selection tests**

Add tests that require the notebook source to contain the exact defaults and branch behavior:

```python
def test_colab_notebook_has_public_tag_fallback() -> None:
    notebook = json.loads(
        Path("notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb").read_text(encoding="utf-8")
    )
    sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "https://github.com/kuotunyu/WoundScope.git" in sources
    assert "WOUNDSCOPE_GIT_URL" in sources
    assert "WOUNDSCOPE_GIT_REF" in sources
    assert "v0.1.0" in sources
    assert "if source_zip.is_file():" in sources
    assert "git', 'clone'" in sources or '"git", "clone"' in sources
    assert "rev-parse" in sources
    assert "status" in sources and "--porcelain" in sources
```

Add an executable fallback test that monkeypatches `subprocess.run`, returns a 40-character SHA from `git rev-parse`, returns an empty string from `git status --porcelain`, executes the source-selection cell without a ZIP, and asserts the clone uses `--branch v0.1.0` and the artifact directory uses the resolved SHA prefix.

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_notebook_release.py -q
```

Expected: the new public fallback tests fail because the notebook raises `FileNotFoundError` and contains no GitHub source defaults.

- [ ] **Step 3: Implement the minimal dual-source notebook flow**

Change the first source cell to define Drive paths without rejecting a missing ZIP. Change the second source cell to preserve the current ZIP manifest verification under `if source_zip.is_file():`; otherwise:

```python
git_url = os.environ.get(
    "WOUNDSCOPE_GIT_URL", "https://github.com/kuotunyu/WoundScope.git"
)
git_ref = os.environ.get("WOUNDSCOPE_GIT_REF", "v0.1.0")
project_dir = runtime_root / "WoundScope_public_source"
if project_dir.exists():
    shutil.rmtree(project_dir)
subprocess.run(
    ["git", "clone", "--filter=blob:none", "--branch", git_ref, "--depth", "1", git_url,
     str(project_dir)],
    check=True,
)
source_commit = subprocess.run(
    ["git", "-C", str(project_dir), "rev-parse", "HEAD"],
    check=True, capture_output=True, text=True, encoding="utf-8",
).stdout.strip()
checkout_status = subprocess.run(
    ["git", "-C", str(project_dir), "status", "--porcelain"],
    check=True, capture_output=True, text=True, encoding="utf-8",
).stdout.strip()
if checkout_status:
    raise RuntimeError("Public source checkout is not clean")
```

Apply the existing lowercase 40-character SHA validation to both source paths before constructing `artifact_dir`.

- [ ] **Step 4: Verify GREEN and private-flow regression**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_notebook_release.py -q
```

Expected: all notebook tests pass, including existing private ZIP manifest and diagnostic tests.

- [ ] **Step 5: Commit Task 1**

```powershell
git add tests/test_notebook_release.py notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb
git commit -m "feat(colab): add public v0.1.0 source fallback"
```

---

### Task 2: Versioned author, repository, and README metadata

**Files:**
- Create: `tests/test_release_metadata.py`
- Create: `docs/releases/v0.1.0.md`
- Modify: `CITATION.cff`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `PROJECT_PLAN.md`

**Interfaces:**
- Consumes: approved author `kuotunyu`, repository URL, version `0.1.0`, release date `2026-08-04`.
- Produces: machine-readable citation/package metadata and a working public Colab/Release navigation path.

- [ ] **Step 1: Write failing release metadata tests**

Create tests using `tomllib`, `yaml.safe_load`, and plain README text assertions:

```python
def test_release_identity_and_repository_urls() -> None:
    cff = yaml.safe_load(Path("CITATION.cff").read_text(encoding="utf-8"))
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert cff["authors"] == [{"name": "kuotunyu"}]
    assert cff["version"] == "0.1.0"
    assert str(cff["date-released"]) == "2026-08-04"
    assert cff["repository-code"] == "https://github.com/kuotunyu/WoundScope"
    assert pyproject["project"]["authors"] == [{"name": "kuotunyu"}]
    assert pyproject["project"]["urls"]["Repository"].endswith("kuotunyu/WoundScope")
```

```python
def test_readme_exposes_public_colab_and_reproducible_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "https://colab.research.google.com/github/kuotunyu/WoundScope/blob/main/" in readme
    assert "uv sync --all-extras --frozen" in readme
    assert "$env:WOUNDSCOPE_MODEL_PATH" in readme
    assert "set WOUNDSCOPE_MODEL_PATH" not in readme
    assert "releases/tag/v0.1.0" in readme
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py -q
```

Expected: failures show generic authors, old release date, missing URLs, relative Colab badge, non-frozen sync, and CMD syntax.

- [ ] **Step 3: Implement metadata and zh-TW release documentation**

Set the approved author and URLs, update README commands and Colab badge, explain ZIP-first／Public-tag fallback behavior, and add `docs/releases/v0.1.0.md` containing the exact verified bundle size/hash/source plus limitations. Update the stale final `PROJECT_PLAN.md` review-gate paragraph to state that implementation and public release are complete; update its citation contract to `kuotunyu` with optional ORCID omitted.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py tests\test_notebook_release.py -q
```

Expected: metadata, README, and notebook tests pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add CITATION.cff pyproject.toml README.md PROJECT_PLAN.md docs/releases/v0.1.0.md tests/test_release_metadata.py
git commit -m "docs(release): prepare v0.1.0 public metadata"
```

---

### Task 3: Privacy-safe aggregate results visual

**Files:**
- Create: `reports/public/model_comparison.svg`
- Modify: `README.md`
- Modify: `tests/test_release_metadata.py`

**Interfaces:**
- Consumes: verified README/bundle aggregates U-Net Dice `0.8508`, IoU `0.7772`; SegFormer Dice `0.8270`, IoU `0.7437`.
- Produces: one accessible SVG referenced from the README results section.

- [ ] **Step 1: Add a failing SVG contract test**

```python
def test_public_model_comparison_is_aggregate_only_and_matches_results() -> None:
    svg = Path("reports/public/model_comparison.svg").read_text(encoding="utf-8")
    assert "<title>" in svg and "<desc>" in svg
    for value in ("0.8508", "0.7772", "0.8270", "0.7437"):
        assert value in svg
    assert "n=3 seeds" in svg
    assert "official-test" in svg
    assert not any(token in svg.lower() for token in ("patient", ".jpg", ".png", "sample_id"))
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "reports/public/model_comparison.svg" in readme
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py::test_public_model_comparison_is_aggregate_only_and_matches_results -q
```

Expected: FAIL because the SVG does not exist.

- [ ] **Step 3: Create the accessible SVG and README placement**

Create a static 1200×520 SVG with a neutral background, two model groups, paired Dice／IoU horizontal bars on a shared 0–1 scale, direct numeric labels, `<title>`／`<desc>`, and a footer stating `locked official validation · n=3 seeds · not official-test or clinical performance`. Use only the four verified aggregate values; do not embed raster images, JavaScript, external resources, or image-level data.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py -q
```

Expected: all release metadata/visual tests pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add reports/public/model_comparison.svg README.md tests/test_release_metadata.py
git commit -m "docs(results): add privacy-safe model comparison"
```

---

### Task 4: CI least privilege and public security intake

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `SECURITY.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_release_metadata.py`

**Interfaces:**
- Consumes: existing `synthetic-gates` job and sole-maintainer contribution policy.
- Produces: read-only Actions token, manual workflow trigger, concurrency cancellation, private vulnerability guidance, and privacy-safe bug intake.

- [ ] **Step 1: Add failing security/repository tests**

```python
def test_ci_and_public_intake_are_least_privilege() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    security = Path("SECURITY.md").read_text(encoding="utf-8")
    issue_form = Path(".github/ISSUE_TEMPLATE/bug_report.yml").read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in workflow
    assert "workflow_dispatch:" in workflow
    assert "cancel-in-progress: true" in workflow
    assert "private vulnerability reporting" in security.lower()
    for forbidden_upload in ("醫療影像", "模型權重", "secret"):
        assert forbidden_upload in issue_form
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py::test_ci_and_public_intake_are_least_privilege -q
```

Expected: FAIL because the workflow permissions/dispatch/concurrency and security intake files are absent.

- [ ] **Step 3: Implement minimal security files and workflow hardening**

Add top-level workflow configuration:

```yaml
permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

Add `workflow_dispatch:` under `on`. Write `SECURITY.md` in `zh-TW` using GitHub private vulnerability reporting without publishing an email address. Write a GitHub issue form with environment, reproduction, expected/actual behavior, logs, and a required checkbox confirming that no medical image, mask, model weight, token, `.env`, secret, or private artifact is attached.

- [ ] **Step 4: Verify GREEN and parse files**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_release_metadata.py -q
.\.venv\Scripts\python.exe -c "import yaml; yaml.safe_load(open('.github/ISSUE_TEMPLATE/bug_report.yml', encoding='utf-8')); yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"
```

Expected: tests and YAML parsing pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add .github/workflows/ci.yml .github/ISSUE_TEMPLATE/bug_report.yml SECURITY.md tests/test_release_metadata.py
git commit -m "ci(security): harden public release workflow"
```

---

### Task 5: Closeout evidence and complete local release gate

**Files:**
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: Tasks 1–4 commits and fresh verification outputs.
- Produces: exact v0.1.0 pre-publication evidence and no stale current blocker.

- [ ] **Step 1: Run focused and full repository gates**

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
git diff --check
```

Expected: Ruff/format pass and all tests pass with only the two documented legacy ONNX exporter deprecation warnings.

- [ ] **Step 2: Run metadata, privacy, author, and link gates**

Parse notebook JSON/CFF/YAML/TOML, ensure local Markdown links resolve, ensure tracked prohibited artifacts count is zero, ensure default-history author/committer identity count is one and contributor trailer count is zero, and confirm the release ZIP has the exact size and SHA-256 from the design.

- [ ] **Step 3: Run clean-checkout reproduction**

Create a fresh `git archive HEAD` extraction under a new gitignored `artifacts/` directory, install/sync from the clean tree using the existing `.venv` interpreter context, then run Ruff, format, and pytest from that extraction. Do not copy `.env`, data, weights, or local artifacts.

- [ ] **Step 4: Record exact PASS evidence**

Update `PROGRESS.md` with commit SHAs, test count, bundle size/hash, privacy/identity/link/metadata/clean-checkout results, and state that hosted CI／Release／branch protection remain the external post-push gates. Replace the stale current blocker sentence saying M6 still needs release documentation.

- [ ] **Step 5: Commit Task 5**

```powershell
git add PROGRESS.md
git commit -m "docs(progress): record v0.1.0 closeout gate"
```

---

### Task 6: Integrate, publish, and verify v0.1.0

**Files:**
- No new repository files; use verified commits and the local safe result ZIP.

**Interfaces:**
- Consumes: clean closeout branch, `C:\Users\3Hml\Downloads\woundscope_colab_results_c7ec6060f1bd.zip`, GitHub repository admin access.
- Produces: updated `main`, annotated `v0.1.0`, Public GitHub Release asset, branch protection, hosted CI success, and a single GitHub contributor.

- [ ] **Step 1: Review branch history and fast-forward `main`**

Confirm every new commit is authored/committed by `kuotunyu`, has no contributor trailer, and the base is `main`. Fast-forward local `main` to the closeout branch without a merge commit.

- [ ] **Step 2: Push `main` and wait for hosted CI**

```powershell
git push origin main
gh run list --repo kuotunyu/WoundScope --workflow CI --limit 1
```

Watch the run to completion and require `conclusion=success` with zero annotations before tagging.

- [ ] **Step 3: Create and push the annotated release tag**

```powershell
git tag -a v0.1.0 -m "WoundScope v0.1.0"
git push origin v0.1.0
```

Confirm `refs/tags/v0.1.0^{}` resolves to the same commit as `origin/main`.

- [ ] **Step 4: Re-verify and publish the safe result bundle**

Verify the bundle into a new empty gitignored directory:

```powershell
.\.venv\Scripts\python.exe scripts\verify_results_bundle.py `
  --bundle C:\Users\3Hml\Downloads\woundscope_colab_results_c7ec6060f1bd.zip `
  --expected-source-commit c7ec6060f1bd0a813a890b95b50c2855d3c2640c `
  --output artifacts\v0.1.0-release-verification
```

Require `status=verified`, 52 manifest files, exact size/hash, and prohibited artifacts zero. Create the Release using `docs/releases/v0.1.0.md` as notes and attach the original verified ZIP.

- [ ] **Step 5: Configure and read back branch protection**

Set `main` protection with strict `synthetic-gates`, `enforce_admins=false`, no force pushes, and no deletion. Do not require external reviews or create bot commits. Read the protection API back and verify the exact values.

- [ ] **Step 6: Final online audit**

Require all of the following:

```text
repository visibility = PUBLIC
default branch = main
origin/main = local HEAD = v0.1.0 peeled commit
latest main CI = success, annotations = 0
Release v0.1.0 = published with one ZIP asset of 344656 bytes
Release asset SHA-256 after re-download = 6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221
Contributors API = kuotunyu only
default-history author/committer identities = kuotunyu only
working tree = clean
```

If any condition fails, stop and report the actual release-candidate state instead of claiming completion.
