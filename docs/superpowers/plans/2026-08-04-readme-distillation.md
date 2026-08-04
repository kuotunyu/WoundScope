# WoundScope README Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 WoundScope README 重構成作品集優先、30 秒可理解、同時保留可重現證據的正體中文首頁。

**Architecture:** `README.md` 保留單一主要閱讀動線：定位 → 亮點 → 結果 → 直式 pipeline → 快速開始 → 工程可信度 → 限制 → 文件。既有 automated tests 繼續保護 result markers、release metadata 與 privacy contracts；行數、章節、正體中文直式 Mermaid 與 local links 改由本次 deterministic documentation checks 驗證。

**Tech Stack:** GitHub Flavored Markdown、Mermaid、Pytest、Ruff、WoundScope repository privacy audit。

## Global Constraints

- README 與 Mermaid 以正體中文（`zh-TW`）為主，technical proper nouns 保留原文。
- Mermaid 必須使用 `flowchart TD` 的窄版直式單一路徑。
- 不更動 schema-valid aggregate results、scientific protocol、資料治理決策、授權邊界或 medical disclaimer。
- 不增加 official-test、patient-wise 或 clinical performance claims。
- 不加入 data、weights、ONNX binaries、private galleries、image-level artifacts 或 secrets。
- 所有 commit author／committer 只能是 `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`，不得加入 trailers。
- 不使用 GPU、不重跑 training／evaluation、不 push。
- 使用者已核准 human-facing prose 不新增逐字／行數 change-detector test；README 設計本身不變。

## File Structure

- Modify: `README.md` — 對外首頁、主要 action、aggregate results、直式 Mermaid 與安全界線。
- Modify: `PROGRESS.md` — 本輪 README 重構與實際 verification evidence。

---

### Task 1: 實作精簡 README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `reports/public/model_comparison.svg`、README result marker region、v0.1.0／v0.2.0 release URLs、Public Colab URL、Hugging Face Space permission gate。
- Produces: 不超過 140 行、七個主要章節、直式正體中文 Mermaid，並保留現有 release tests 所需 contracts。

- [ ] **Step 1: 記錄既有 README contracts baseline**

Run:

```powershell
uv run pytest tests/test_release_metadata.py tests/test_huggingface_space_metadata.py tests/test_notebook_release.py tests/test_readme_results.py -q
```

Expected: PASS；證明改寫前 Public Colab、release links、PowerShell variables、result markers、aggregate SVG 與 Space permission status 都有保護。

- [ ] **Step 2: 依核准設計重寫 README**

保留四個現有 badges，Hero 使用下列定位與 result proof：

```markdown
# WoundScope

[![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/kuotunyu/WoundScope/blob/main/notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb)
[![Hugging Face Space](https://img.shields.io/badge/Hugging%20Face-Space%20授權確認中-yellow)](#快速開始)
[![CI](https://github.com/kuotunyu/WoundScope/actions/workflows/ci.yml/badge.svg)](https://github.com/kuotunyu/WoundScope/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/kuotunyu/WoundScope)](https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.0)

**從資料治理、可恢復訓練到 ONNX deployment 的可重現足部潰瘍 segmentation pipeline。**

以固定版本 FUSeg 驗證 U-Net 與 SegFormer；最佳 U-Net 在鎖定後 official validation 達到 **Dice 0.8508 ± 0.0035**（`n=3 seeds`）。這是研究用像素分割結果，不是 official-test 或 clinical performance。
```

七個章節的實際內容如下：

1. `## 專案亮點`
   - `可信資料治理`：固定 FUSeg revision、integrity audit、排除 7 張 train exact copies、完整保留 validation 200 張。
   - `可重現實驗`：Group-aware train／dev、AMP、atomic resume、三個固定 seeds、dev-only calibration。
   - `部署級交付`：locked official validation、Bootstrap、ONNX parity、CPU Gradio、privacy-safe handoff。
2. `## 已驗證成果`
   - 先引用 `reports/public/model_comparison.svg`。
   - 原樣保留 `<!-- RESULTS_TABLE_START -->`／`<!-- RESULTS_TABLE_END -->` 與 machine-generated 表格。
   - 用兩句話交代結果來源、U-Net observed Dice 較高但未做 paired significance test，以及非 official-test／非 clinical performance。
3. `## 流程全貌`
   - 使用 spec 核准的八節點 `flowchart TD`。
4. `## 快速開始`
   - 明列 `Python 支援 3.11–3.12。`
   - Colab 為主要入口，說明 `Run all` 是完整 GPU pipeline，artifacts 留在使用者 private Drive。
   - 本機重現只留：

```powershell
uv venv --python 3.12
uv sync --all-extras --frozen
$env:WOUNDSCOPE_DATA_DIR = "data"
.\.venv\Scripts\python.exe scripts\download_data.py
```

   - 以 `<details>` 收納本機 Gradio：

```powershell
$env:WOUNDSCOPE_MODEL_PATH = "artifacts\runs\RUN\model.onnx"
$env:WOUNDSCOPE_CALIBRATION_PATH = "artifacts\runs\RUN\calibration.json"
.\.venv\Scripts\python.exe app\app.py
```

   - 保留 `PERMISSION_PENDING` 與 `docs/huggingface-space-deployment.md`。
5. `## 工程可信度`
   - 用四個短 bullets 濃縮資料、訓練、評估／部署與品質 gates；不列逐項 CLI inventory。
6. `## 限制與安全界線`
   - 保留 no patient ID、official test 無 masks、尚無 external validation、confidence 非 clinical confidence、研究用途／人工複核。
7. `## 文件與 Release`
   - 連到 `docs/releases/v0.2.0.md`、v0.2.0 release、v0.1.0 result release、`PROJECT_PLAN.md`、`DATA_CARD.md`、`MODEL_CARD.md`、`scripts/download_artifacts.md`、`CITATION.cff`、`LICENSE`。

刪除舊 `問題定義與資料`、`方法`、`評估、ONNX 與本機推論`、獨立 `Colab`、獨立 `Gradio demo`、`測試與驗收`、`90 秒 demo 腳本` 與重複說明；其核心事實依上面七節收斂。

- [ ] **Step 3: 執行 README focused contracts 與 deterministic design checks**

Run:

```powershell
uv run pytest tests/test_release_metadata.py tests/test_huggingface_space_metadata.py tests/test_notebook_release.py tests/test_readme_results.py -q
$readme = Get-Content -LiteralPath README.md -Raw -Encoding utf8
if (($readme -split "`n").Count -gt 140) { throw 'README exceeds 140 lines' }
if ($readme -notmatch 'flowchart TD' -or $readme -match 'flowchart LR') { throw 'README Mermaid is not vertical' }
if ($readme -match '^## 90 秒 demo 腳本$') { throw 'Legacy demo section remains' }
Write-Output 'README_DESIGN_CONTRACT_PASS'
```

Expected: tests PASS 且輸出 `README_DESIGN_CONTRACT_PASS`；result markers 恰好各一組，Public Colab、release links、PowerShell variables、aggregate SVG 與 Space permission status 均保留。

- [ ] **Step 4: 建立 owner-only implementation commit**

```powershell
git add -- README.md
git diff --cached --check
git -c user.name='kuotunyu' -c user.email='61350295+kuotunyu@users.noreply.github.com' commit --author='kuotunyu <61350295+kuotunyu@users.noreply.github.com>' -m 'docs: distill project README'
```

Expected: author／committer 都是 `kuotunyu`，commit message 無 trailers。

---

### Task 2: 完整驗證與進度紀錄

**Files:**
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: Task 1 的 committed README 與 test contract。
- Produces: exact PASS/FAIL evidence、乾淨 working tree 與 owner-only closeout commit。

- [ ] **Step 1: 驗證 README local links**

Run:

```powershell
$text = Get-Content -LiteralPath README.md -Raw -Encoding utf8
$missing = [regex]::Matches($text, '\[[^\]]+\]\((?!https?://|#)([^)]+)\)') | ForEach-Object { $_.Groups[1].Value.Split('#')[0] } | Where-Object { $_ -and -not (Test-Path -LiteralPath $_) } | Sort-Object -Unique
if ($missing) { throw "Missing README targets: $($missing -join ', ')" }
Write-Output 'README_LOCAL_LINKS_PASS'
```

Expected: `README_LOCAL_LINKS_PASS`。

- [ ] **Step 2: 執行完整 repository gates**

Run:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run python scripts/audit_repository_privacy.py --repository .
git diff --check
```

Expected: 全部 PASS；只有既有、已記錄的 ONNX warnings 可接受。

- [ ] **Step 3: 人工檢查最終 README**

確認：Hero 在首屏交代定位與最佳 verified result；七個章節依 contract 排列；Mermaid 為八節點直式單一路徑；主要 action 是 Public Colab；沒有誇大 medical／official-test／patient-wise claim；內容不超過 140 行。

- [ ] **Step 4: 在 PROGRESS 頂端新增 session evidence**

新增 `2026-08-04 — README 精簡與正體中文 Mermaid`，記錄：目標、README／test contract 變更、focused/full gate 實際通過數、privacy audit、無 GPU／training／results 變更、未 push。

- [ ] **Step 5: 重跑 documentation-sensitive gates**

Run:

```powershell
uv run pytest tests/test_release_metadata.py tests/test_huggingface_space_metadata.py tests/test_notebook_release.py tests/test_readme_results.py -q
uv run python scripts/audit_repository_privacy.py --repository .
git diff --check
```

Expected: PASS。

- [ ] **Step 6: 建立 owner-only closeout commit 並稽核 history**

```powershell
git add -- PROGRESS.md
git diff --cached --check
git -c user.name='kuotunyu' -c user.email='61350295+kuotunyu@users.noreply.github.com' commit --author='kuotunyu <61350295+kuotunyu@users.noreply.github.com>' -m 'docs: record README verification'
git log -3 --format='%H%x09%an <%ae>%x09%cn <%ce>%x09%s'
git log -3 --format='%B' | Select-String -Pattern 'Co-authored-by|Signed-off-by|Reviewed-by'
git status --short
```

Expected: 近期 commits 的 author／committer 都是唯一的 `kuotunyu`、trailer scan 無輸出、working tree clean；不 push。
