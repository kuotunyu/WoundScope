# WoundScope 實作進度

> 本文件保存目前可驗證狀態與續作入口。穩定規格與科學 protocol 請見 `PROJECT_PLAN.md`。  
> 所有完成狀態都必須有實際測試或檢查證據；沒有證據不得標示完成。

## Current status

| 欄位 | 內容 |
|---|---|
| Project state | `IMPLEMENTING / M1_BLOCKED` |
| Current milestone | M1 — Data integrity scientific gate；M2–M6 可離線部分已平行實作 |
| Last updated | 2026-07-19（Asia/Taipei） |
| Last verified state | Official 810/200/200 integrity audit 完成；Ruff PASS、50 tests PASS、CPU Docker build/app smoke PASS |
| Active blocker | Pinned official split 有 7 組 train–validation exact duplicates；mitigation 尚未由使用者確認 |
| Next action | 確認是否採建議的 `exclude_train`，再把 source repo 放到 Drive 並執行 Colab quick mode |
| External actions | Local data 已下載且 gitignored；建立 local CPU Docker image；無 GPU training、remote、push 或 upload |

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
| M1 — Data integrity | Blocked | Synthetic + official data validation 通過 | 結構/count PASS；7 exact cross-split findings 需科學決策 |
| M2 — Vertical slice | Completed | Tiny end-to-end + ONNX parity 通過 | one epoch/save/resume、prediction、ONNX/app synthetic gates PASS |
| M3 — Training/Colab | In review | CPU mini-train、resume、notebook、Colab quick gate 通過 | 兩正式模型 CPU optimizer step + notebook structure PASS；Colab quick 待執行 |
| M4 — Evaluation/calibration | In review | Metrics/bootstrap/calibration/confidence/gallery gates 通過 | unit gates PASS；full weights/locked validation artifacts 尚無 |
| M5 — Inference/demo | In review | CPU/CUDA/ONNX/benchmark/app gates 通過 | CPU PyTorch/ONNX/app/benchmark PASS；CUDA smoke 待 Colab／本機另行執行 |
| M6 — Release | In review | CI/Docker/clean-clone/data-secret audit 通過 | 文件/CI/CPU Docker/secret audit PASS；clean-commit reproduction 與 hosted CI 待後續 |

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

### 2026-07-19 — M1 integration 與 M2–M6 offline gates

- `scripts/download_data.py --skip-download --allow-cross-split-exact` → structural PASS；train 810 masks、validation 200 masks、test 200 images／0 masks；internal train 650、dev 160。
- Official warning：`validation/labels/0233.png` 有 84 個位於 positive boundary 的 gray-32 pixels；以 threshold 128 正規化並保留 `mask_antialias_normalized` warning。
- Official duplicate audit：58 個 duplicate/near-duplicate groups；7 組 train–validation exact SHA-256 duplicates；另有 cross-split pHash warnings。`--allow-cross-split-exact` 只允許產生報告，不代表 training approval。
- `uv sync --all-extras --frozen` → PASS；Windows CJK path 使用 isolated Python 3.12。
- `python -m ruff check .` → PASS。
- `python -m ruff format --check .` → PASS；49 files formatted。
- `python -m pytest -q` → PASS；50 passed，2 個 PyTorch legacy ONNX exporter deprecation warnings，無 test failure。
- 正式 model gates：EfficientNet-B0 U-Net 與 tiny-config SegFormer-B0 均完成 CPU forward + finite optimizer step；未下載 pretrained weights。
- ONNX gate：TinyUNet fixed-spatial export、logit allclose、binary-mask parity、CPU OnnxPredictor 與 benchmark schema PASS。
- `docker build -t woundscope:local-test .` → PASS；改用 official CPU wheel，避免 Space image 安裝 CUDA runtime。
- `docker run --rm woundscope:local-test ... build_demo()` → PASS；`torch 2.13.0+cpu`、Gradio app build 正常；image size 492,079,887 bytes。
- `SCRIPT_HELP_PASS=9`、`CFF_PARSE_PASS`、`TRACKED_ARTIFACT_AUDIT_PASS`、`GIT_REMOTE_COUNT=0`。
- `quick_validate.py .agents/skills/woundscope-development` → PASS；新增「data report 不等於 training approval」guardrail。
- GPU/full training：未執行；Google Colab quick：待使用者啟動。

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
| `PROJECT_PLAN.md` | Active contract | Review gate 已解除；exact-duplicate mitigation 是 open decision |
| `PROGRESS.md` | Active | 即時進度、證據與續作入口 |
| `.env` | Preserved and ignored | 內容未讀出、未修改、未追蹤 |
| M0 source/config/tests | Created and verified | Package、YAML config、CLI、AGENTS、skill、license 與 ignore rules |
| `data/raw/fuseg/` | Local, gitignored | Pinned official sparse checkout；不可 commit／重傳 |
| `data/manifests/` | Local, gitignored | `data_manifest.csv`、`data_summary.json` 與 duplicate findings |
| M2–M5 source/tests | Created and CPU verified | data/model/loss/train/evaluate/calibration/ONNX/inference/Gradio stack |
| `notebooks/01_train_colab.ipynb` | Created, structure verified | Drive persistence、quick/full、resume、calibration、ONNX、sample prediction |
| `artifacts/handoff/WoundScope_colab_source.zip` | Local, gitignored | 78 safe source files、229,299 bytes、SHA-256 `3489A804EEFA73829259B9F75D174AB46F33641E54AE8AC3117A1DA34BDE17D4` |
| Release files | Created and verified | README/cards/CFF/CI/Docker/.env.example/artifact handoff |
| Model/training artifacts | None | 無 checkpoint、ONNX performance artifact 或 full-training result |

## Blockers and risks

### Active blocker

- Pinned FUSeg official split 實測有 7 組 train–validation exact image duplicates。推薦 mitigation 是從 training pool 排除 `train/0121`、`0569`、`0636`、`0803`、`0980`、`0983`、`0997`，保留官方 validation 200 張並另做 deduplicated sensitivity summary。此選擇尚未由使用者確認，因此 M1 不標示完成，training CLI 與 notebook 預設停止。
- M3 的 Colab GPU quick run 需要使用者明早開啟 runtime；其餘 code path 已以 CPU/synthetic 驗證。

### Known risks

- FUSeg challenge design 只寫「CC BY NC」，缺少版本與完整 legal text；禁止預設 data／weights 可再散布。
- 無 patient ID，無法建立 patient-wise split，可能存在 source/patient correlation。
- Official test masks 未公開，不能宣稱 test-set quantitative performance。
- Exact duplicate 與 pHash near-duplicate 可能高估 generalization；pHash distance 0 不等同 exact bytes 或相同 patient。
- 本機可能有其他工作負載；full training 預設只在 Colab 執行。

## Next actions

1. 使用者確認 exact-duplicate mitigation；若接受推薦方案，將 notebook 的 `CROSS_SPLIT_POLICY` 設為 `"exclude_train"`。
2. 在 `PROJECT_PLAN.md` Decision Log 鎖定選擇、重跑 M1 gate，建立下一個 local milestone commit；仍不 push。
3. 將 `artifacts/handoff/WoundScope_colab_source.zip` 上傳為 Google Drive `MyDrive/WoundScope_colab_source.zip`，開啟 notebook 後 Run all quick mode。
4. 取得 Drive quick artifacts 後驗證 resume、provenance、calibration、ONNX 與 sample predictions；quick metrics 不進 README。
5. Full comparison／multi-seed training 必須等 quick gate 與 loss-selection protocol 通過後再執行。

## Session log

### 2026-07-19 — M1 audit 與 downstream CPU implementation

**目標**

- 在不使用 RTX 4090、不跑 full training、不 push/upload 的前提下，完成能安全離線驗證的 WoundScope pipeline。

**變更**

- 下載 pinned FUSeg、建立 manifest／duplicate report／group-aware internal split，並將結構錯誤與科學警告分離。
- 實作 conservative augmentation、兩 losses、U-Net、SegFormer、resumable training、metrics/bootstrap、calibration、TTA confidence、error selection、ONNX、predict/evaluate/benchmark 與 Gradio。
- 建立 Colab quick/full notebook、Drive handoff、README、cards、CFF、CI、Docker 與 verified-results-only README updater。
- Training CLI 新增 explicit cross-split policy；預設 `error`，`exclude_train` 才會排除 exact train copies。
- Docker 首次 audit 發現一般 PyPI PyTorch 會拉入 CUDA 13 dependencies；只停止本次 WoundScope build process，改用 official CPU wheel 後重建成功，未操作其他 Docker workloads。

**驗證**

- Official integration counts/integrity PASS，但 scientific duplicate gate BLOCKED。
- Ruff/format PASS；50 pytest PASS；9 scripts help PASS；skill valid；CFF parse；Git artifact/remote audit PASS。
- CPU Docker build 與 Gradio import/build smoke PASS；本機 GPU 未使用。

**Artifacts**

- `data/manifests/data_manifest.csv`、`data/manifests/data_summary.json`（gitignored）
- `notebooks/01_train_colab.ipynb`
- `artifacts/handoff/WoundScope_colab_source.zip`（gitignored safe source snapshot）
- `artifacts/` 尚無 model run；Docker local tag `woundscope:local-test`

**決策／偏差**

- 發現 7 組 exact train–validation duplicates 是新 evidence，已在 `PROJECT_PLAN.md` Decision Log 建立 Open decision；未擅自把推薦 mitigation 鎖定。
- 因 M1 被 scientific gate 擋住，M0 後的變更尚未建立 milestone boundary commit。

**未完成與下一步**

- 明早確認 `exclude_train` 或指定其他 mitigation；再執行 Colab quick gate。

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
