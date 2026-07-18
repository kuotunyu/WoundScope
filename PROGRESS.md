# WoundScope 實作進度

> 本文件保存目前可驗證狀態與續作入口。穩定規格與科學 protocol 請見 `PROJECT_PLAN.md`。  
> 所有完成狀態都必須有實際測試或檢查證據；沒有證據不得標示完成。

## Current status

| 欄位 | 內容 |
|---|---|
| Project state | `IMPLEMENTING` |
| Current milestone | M1 — Data integrity |
| Last updated | 2026-07-19（Asia/Taipei） |
| Last verified state | M0 scaffold 與 repo-local skill 已通過 gates；local Git 無 remote；尚未執行 training |
| Active blocker | 無 |
| Next action | 下載 pinned FUSeg revision、驗證資料並建立 gitignored manifest/internal split |
| External actions | Local Git 已初始化；無 remote、無 push、無 training |

## Resume checklist

下次開始工作時依序執行：

1. 讀取 `PROJECT_PLAN.md` 的 Review gate、Decision Log 與當前 milestone。
2. 讀取本文件的 Current status、Blockers、Test evidence 與 Next actions。
3. 檢查 workspace／Git 狀態，不讀出或回報 `.env` values。
4. 只執行 current milestone 範圍內的工作。
5. 跑該 milestone 的 gate；記錄成功與失敗，不隱藏 failed checks。
6. 更新本文件的狀態、artifact、測試證據、決策與下一步。
7. 只有 gate 全數通過後才建立 milestone boundary local commit；不得 push。

## Milestone dashboard

| Milestone | 狀態 | 完成條件 | 最近證據 |
|---|---|---|---|
| Pre-implementation docs | Completed | 兩份文件建立並經使用者確認 | 2026-07-19 使用者解除 review gate |
| M0 — Governance/scaffold | Completed | Ignore/secret/config/import/Ruff/pytest gates 通過 | Ruff PASS；5 tests PASS；skill valid；ignore PASS |
| M1 — Data integrity | In progress | Synthetic + official data validation 通過 | 正在建立 downloader/validator |
| M2 — Vertical slice | Not started | Tiny end-to-end + ONNX parity 通過 | — |
| M3 — Training/Colab | Not started | CPU mini-train、resume、notebook、Colab quick gate 通過 | — |
| M4 — Evaluation/calibration | Not started | Metrics/bootstrap/calibration/confidence/gallery gates 通過 | — |
| M5 — Inference/demo | Not started | CPU/CUDA/ONNX/benchmark/app gates 通過 | — |
| M6 — Release | Not started | CI/Docker/clean-clone/data-secret audit 通過 | — |

允許的狀態值：`Not started`、`In progress`、`Blocked`、`In review`、`Completed`。

## Locked decision snapshot

- Data source revision：`42a272dfe0679f20675e826385925cb7562934b6`。
- Verified scale：train 810 pairs、validation 200 pairs、test 200 images／0 public masks。
- Split：official train 建 internal train/dev；official validation locked；official test 不做調參或 metrics。
- Models：EfficientNet-B0 U-Net baseline、SegFormer-B0 advanced。
- Losses：BCE+Dice、Focal+Tversky。
- Full experiments：seed 42 ablation；selected configs 使用 seeds 42/43/44。
- Confidence：temperature scaling + threshold sweep + 2-view horizontal-flip TTA。
- Code license：Apache-2.0；FUSeg data／weights 不包含在內。
- Language：人讀文件與 UI 以正體中文為主，專有名詞與程式介面維持英文。
- Publication：目前不設定 remote、不 push、不上傳 data 或 weights。

重大調整必須先更新 `PROJECT_PLAN.md` Decision Log；本區只同步摘要，不取代完整規格。

## Test and verification evidence

### 2026-07-19 — M0 gate

- `git check-ignore -v -- .env .venv data/data_manifest.csv artifacts/model.onnx reports/generated/example.png` → PASS；所有敏感／大型 artifacts 均命中規則。
- `git remote` → PASS；沒有 remote。
- `uv run ruff check .` → PASS。
- `uv run ruff format --check .` → PASS；5 files formatted。
- `uv run pytest -q` → PASS；5 passed。
- `uv run woundscope show-config ... --set training.batch_size=4` → PASS；base/model/mode/CLI merge 與 stable hash 正常。
- `quick_validate.py .agents/skills/woundscope-development` → PASS；repo-local skill valid。
- 初次 `.venv` 使用 Anaconda Python 3.10 時，editable install 在中文 workspace path 發生 cp950 decode failure；已改用 bundled Python 3.12.13 重建隔離環境並將規則加入 project skill。
- Skill initializer 初次以 Windows code page 寫壞中文 UI metadata；已修復為 UTF-8 並重新驗證。

### 2026-07-19 — Pre-implementation inspection

- Working directory：`C:\Users\3Hml\Desktop\CC_github部隊\長照\2_WoundScope`
- Read-only workspace inspection：通過。
- Git metadata：不存在。
- Existing files before documentation：只有 `.env`。
- `.env` values：未讀出、未記錄、未修改。
- Document structure validation：PASS；已確認必要章節、七個 milestones、Decision Log 與 `REVIEW_GATE` 狀態。
- Encoding note：Windows PowerShell 5.1 讀取 UTF-8 Markdown 時必須明確使用 `Get-Content -Encoding UTF8`；未指定 encoding 的首次比對產生 false negative，改用 UTF-8 後通過。
- Tests：Not applicable；目前尚無程式碼或 test suite。
- Training／GPU workload：未執行。
- Network mutation／publication：未執行。

## Artifacts

| Artifact | 狀態 | 說明 |
|---|---|---|
| `PROJECT_PLAN.md` | Created, pending review | 穩定 implementation contract |
| `PROGRESS.md` | Created, pending review | 即時進度與續作入口 |
| `.env` | Preserved | 現有檔案，內容未修改；M0 必須先加入 ignore |
| M0 source/config/tests | Created and verified | Package、YAML config、CLI、AGENTS、skill、license 與 ignore rules |
| Code/data/model artifacts | No data/model artifacts | 尚未下載 FUSeg、未 training |

## Blockers and risks

### Active blocker

- 無。

### Known risks

- FUSeg challenge design 只寫「CC BY NC」，缺少版本與完整 legal text；禁止預設 data／weights 可再散布。
- 無 patient ID，無法建立 patient-wise split，可能存在 source/patient correlation。
- Official test masks 未公開，不能宣稱 test-set quantitative performance。
- 目前 repo 尚未有 `.gitignore`，因此正式初始化 Git 前必須先保護 `.env`、data 與 artifacts。
- 本機可能有其他工作負載；full training 預設只在 Colab 執行。

## Next actions

1. 建立 `download_data.py` 與 reusable data validation module。
2. 以 synthetic fixtures 測試 pairing、corruption、size、mask 與 duplicate cases。
3. Sparse-checkout pinned FUSeg revision 並產生 `data_manifest.csv`。
4. 驗證 official counts、cross-split findings 與 deterministic internal split。
5. 記錄 M1 gate 後進入 CPU vertical slice。

## Session log

### 2026-07-19 — M0 governance 與 scaffold

**目標**

- 解除 review gate，建立安全、可安裝、可續作的 repository foundation。

**變更**

- 建立 ignore、Apache-2.0、`pyproject.toml`、YAML configs、package/CLI、config tests、AGENTS 與 repo-local skill。
- 初始化 local Git `main`，保持無 remote。
- 以 UTF-8-capable Python 3.12 建立 `.venv` 與 `uv.lock`。

**驗證**

- Ruff、format、5 pytest cases、CLI config、skill validation 與 ignore audit 全數 PASS。

**Artifacts**

- `.agents/skills/woundscope-development/`
- `configs/`、`src/woundscope/`、`tests/test_config.py`
- `.venv/`（gitignored）與 `uv.lock`

**決策／偏差**

- 無 scientific protocol 偏差；Windows CJK path 必須使用 UTF-8-capable Python 的 pitfall 已固化到 skill。

**未完成與下一步**

- 執行 M1 data acquisition/integrity。

### 2026-07-19 — 建立 pre-implementation 文件

**目的**

- 將已討論並鎖定的完整計畫落地為可續作文件。
- 在任何程式、Git 或 data mutation 前建立明確 review gate。

**完成**

- 建立 `PROJECT_PLAN.md`，記錄 scope、資料與授權、科學 protocol、interfaces、artifacts、七個 milestones、tests、release 文件與 Decision Log。
- 建立 `PROGRESS.md`，記錄 current state、resume checklist、milestone dashboard、evidence、risks 與 next actions。
- 保留既有 `.env`，未讀出或修改 values。

**未執行**

- Git 初始化、remote、commit 或 push。
- 程式 scaffold、依賴安裝、資料下載、測試或 training。

**交接點**

- 狀態為 `REVIEW_GATE`。
- 下一個可執行工作是使用者確認後開始 M0。

## Session update template

後續每次工作在 Session log 頂端新增一節，格式如下：

```markdown
### YYYY-MM-DD — 簡短主題

**目標**
- ...

**變更**
- ...

**驗證**
- `實際命令` → PASS/FAIL，關鍵輸出...

**Artifacts**
- path、hash 或 run ID...

**決策／偏差**
- 無；或連結到 PROJECT_PLAN.md Decision Log...

**未完成與下一步**
- ...
```
