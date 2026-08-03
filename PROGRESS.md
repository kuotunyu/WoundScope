# WoundScope 實作進度

> 本文件保存目前可驗證狀態與續作入口。穩定規格與科學 protocol 請見 `PROJECT_PLAN.md`。  
> 所有完成狀態都必須有實際測試或檢查證據；沒有證據不得標示完成。

## Current status

| 欄位 | 內容 |
|---|---|
| Project state | `V0.1.0_RELEASE_CANDIDATE / M6_COMPLETED` |
| Current milestone | v0.1.0 收尾 — 本機、privacy、作者與 clean-checkout gates 已通過；等待 hosted CI、tag 與 GitHub Release |
| Last updated | 2026-08-04（Asia/Taipei） |
| Last verified state | v0.1.0 candidate：Ruff／format／113 tests／privacy／links／metadata／唯一 `kuotunyu` Git identity／clean-checkout reproduction／safe result ZIP hash 全部 PASS |
| Active blocker | 無；只剩需在 GitHub 執行的 hosted CI、tag、Release 與 `main` protection gates |
| Next action | Fast-forward `main`、push、等待 hosted CI 成功，再建立 `v0.1.0` tag／Release 並完成線上稽核 |
| External actions | Public `https://github.com/kuotunyu/WoundScope` 已存在；本輪 v0.1.0 candidate 尚未 push／tag／release，private artifacts 未上傳 |

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
| M1 — Data integrity | Completed | Synthetic + official data validation 通過 | 2026-08-03 `exclude_train` gate：7 train copies excluded、validation 200 retained、group isolation PASS |
| M2 — Vertical slice | Completed | Tiny end-to-end + ONNX parity 通過 | one epoch/save/resume、prediction、ONNX/app synthetic gates PASS |
| M3 — Training/Colab | Completed | CPU mini-train、resume、notebook、Colab quick gate 通過 | A100 staged quick/full、AMP、deliberate resume、loss selection與三-seed final completed |
| M4 — Evaluation/calibration | Completed | Metrics/bootstrap/calibration/confidence/gallery gates 通過 | Locked official validation、dev calibration、2,000 bootstrap、五類 private gallery completed |
| M5 — Inference/demo | Completed | CPU/CUDA/ONNX/benchmark/app gates 通過 | 六組 CUDA→ONNX parity、CPU benchmark completed；PyTorch/ONNX/app tests PASS |
| M6 — Release | Completed | CI/Docker/clean-clone/data-secret audit 通過 | 文件/CI/CPU Docker/secret/96-file clean-checkout reproduction、GitHub hosted CI 與 Contributors audit PASS |

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
- Publication：已授權公開 `kuotunyu/WoundScope` 的程式碼與 privacy-safe aggregate results；不上傳 data、weights、private galleries 或 image-level artifacts；GitHub Contributors 只允許 `kuotunyu`。
- Cross-split policy：`exclude_train`；只排除 7 張 exact train copies，official validation 200 張完整保留。

重大調整必須先更新 `PROJECT_PLAN.md` Decision Log；本區只同步摘要，不取代完整規格。

## Test and verification evidence

### 2026-08-04 — v0.1.0 closeout candidate

- Public Colab source fallback 已以 TDD 完成：Drive 中存在 `WoundScope_colab_source.zip` 時保留 immutable ZIP／manifest／checksum 流程；缺少 ZIP 時改從 `https://github.com/kuotunyu/WoundScope.git` checkout 預設 tag `v0.1.0`，解析 40-character commit SHA、確認 clean checkout，並維持相同 `project_dir`／`source_commit`／artifact interface。
- Release metadata 已完成：`CITATION.cff`、`pyproject.toml`、README、`PROJECT_PLAN.md` 與 `docs/releases/v0.1.0.md` 皆使用 `kuotunyu` 身分與 `zh-TW`-first 敘述；Colab badge 使用可直接開啟的 GitHub notebook URL。
- Privacy-safe aggregate 視覺 `reports/public/model_comparison.svg` 只包含 locked official-validation aggregate Dice／IoU、`n=3 seeds` 與非 official-test／非臨床聲明，不含影像、mask、image-level metrics 或可識別資料；瀏覽器 render visual inspection PASS。
- CI/security hardening：workflow 支援 manual dispatch、read-only permissions、concurrency cancellation，third-party actions 維持 immutable SHA pin；新增 `zh-TW` bug report form 與 `SECURITY.md`，明確禁止公開 medical images／masks／weights／ONNX／`.env`／token／private artifacts。
- GitHub Private Vulnerability Reporting preflight 原為 disabled；依 `SECURITY.md` 的唯一私密通報 contract 啟用後由 API 讀回 `enabled=true`，外部 security-intake blocker 已解除。
- TDD／release commits：`5e32d12`（Colab fallback）、`29aa179`（metadata/docs）、`9d11594`（aggregate SVG）、`4462000`（CI/security）。
- Final local gate：`uv run ruff check --no-cache .` PASS；`uv run ruff format --check .` → `64 files already formatted`；`uv run pytest -q` → `113 passed`，只有 2 個既知 legacy ONNX exporter deprecation warnings；`git diff --check` PASS。
- Tracked privacy audit：103 tracked files，forbidden data／manifest／`.env`／generated galleries／checkpoints／ONNX artifacts 為 0；17 份 Markdown local-link audit PASS；notebook JSON、CFF／workflow／issue YAML 與 `pyproject.toml` parse PASS。
- Git identity audit：全部 author／committer 唯一為 `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`；`Co-authored-by`／`Signed-off-by` trailers 為 0。
- Clean-checkout reproduction：以 `git archive` 從 candidate `4462000ec846` 匯出全新 source snapshot，使用 UTF-8-capable Python 3.12.13 與 `uv sync --all-extras --frozen` 安裝 96 packages；Ruff／format／113 tests 全部 PASS。
- Safe result bundle 再驗證：`woundscope_colab_results_c7ec6060f1bd.zip` 為 344,656 bytes；SHA-256 `6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221`，與既有 verified c7 evidence 完全一致。
- GPU／training：本輪未使用 GPU、未重跑 training；所有 v0.1.0 closeout gates 都是 CPU／metadata／Git／privacy checks。
- External pending gates：candidate 尚未 push；必須先由 GitHub hosted CI 驗證最終 commit，成功後才可建立 annotated `v0.1.0` tag、GitHub Release、safe result ZIP asset 與 `main` branch protection。

### 2026-08-04 — GitHub Public release preflight

- 使用者明確授權 Public `kuotunyu/WoundScope`；README、Description、About 以正體中文（`zh-TW`）為主，技術專有名詞保留原文。
- GitHub CLI 已登入 `kuotunyu`；目標 repository 尚不存在，無名稱衝突。
- 原始 17-commit history 只有 root commit 使用 placeholder `WoundScope contributors <woundscope@local.invalid>`；無 `Co-authored-by`、`Signed-off-by` 或 `Reviewed-by` trailers。
- 已建立並驗證 gitignored recovery bundle `artifacts/pre_github_publish_f3e3b9f.bundle`，306,125 bytes，SHA-256 `EA00EDF71E0C714715EF09688E35413575A74F5BDCC62E25ECF93E2723D01F7E`。
- Default-history placeholder author 已正規化為 `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`；17 commits 的 author/committer 統一，改寫前後 HEAD tree hash 完全一致。
- 舊 commit graph 以 annotated tag `provenance-pre-publication-f3e3b9f` 保留，training source `c7ec6060f1bd0a813a890b95b50c2855d3c2640c` 仍可從該 tag reachability 驗證。
- Public repository 已建立於 `https://github.com/kuotunyu/WoundScope`；visibility=`PUBLIC`、default branch=`main`，Description 與 topics 已設定為 `zh-TW`-first。
- GitHub hosted CI run `30831760839` 於 `main` 成功完成；dependency sync、Ruff、format、107 tests 與 prohibited-artifact audit 全部 PASS。
- GitHub Contributors API（含 anonymous contributors）只回傳 `kuotunyu`，18 contributions；無 bot、placeholder 或共同作者。
- Hosted CI 的 Node.js 20 deprecation annotation 已以 SHA-pinned `actions/checkout` v6.1.0 與 `astral-sh/setup-uv` v8.1.0 修正；本次 release commit 將再由 hosted CI 驗證。

### 2026-08-03 — Verified c7 full-run results ingestion

- Downloaded safe ZIP：`woundscope_colab_results_c7ec6060f1bd.zip`；344,656 bytes；SHA-256 `6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221`，與 Colab stage record 完全一致。
- `scripts/verify_results_bundle.py` clean extraction → `status=verified`；training source `c7ec6060f1bd0a813a890b95b50c2855d3c2640c`；52 manifest members，另含 bundle manifest；prohibited artifacts 0。
- Provenance：training source 維持 c7；handoff implementation `8345176593e3fe5a3c95e2f053306229e5a09455`；safe bundle 不含 weights、ONNX binaries、來源影像、image-level metrics 或 private galleries。
- Experiment lock：兩個架構皆由 internal dev 選出 `bce_dice`；final seeds 固定 42/43/44；official validation 200 張未參與 selection、checkpoint、threshold 或 temperature fitting。
- EfficientNet-B0 U-Net official-validation aggregate：Dice `0.8508±0.0035`（image-cluster bootstrap 95% CI `0.8218–0.8768`）、IoU `0.7772±0.0039`、precision `0.8581±0.0056`、recall `0.9039±0.0032`、specificity `0.9989±0.0000`。
- SegFormer-B0 aggregate：Dice `0.8270±0.0040`（95% CI `0.7973–0.8550`）、IoU `0.7437±0.0053`、precision `0.8326±0.0038`、recall `0.8832±0.0045`、specificity `0.9988±0.0000`。
- 六組 final ONNX parity 與 CPU benchmark、六份 calibration/provenance/config/history/public chart 均 completed；U-Net observed Dice 較高只描述此 locked split，未做 paired significance test，不宣稱 official-test、patient-wise、外部或臨床效能。
- 第一次本機 re-extract 到非空 evidence directory 被安全拒絕（expected）；改用新的空白 gitignored directory後完整驗證 PASS，沒有覆蓋既有證據。
- Final repository gate：Ruff check PASS；Ruff format check `63 files already formatted`；pytest `107 passed`（僅 2 個既知 legacy ONNX exporter deprecation warnings）；`git diff --check` PASS。
- Release test 原先硬性要求 README 一定包含「待填」，與 verified completed-result 狀態矛盾；已移除該過時文字假設，保留兩個 results markers 各一次的 release contract，完整 suite 重跑 PASS。
- Privacy/publication audit：96 tracked files；forbidden tracked artifacts 0；Git remotes 0；`.env`、manifest 與兩個 verified extraction directories 均由 `.gitignore` 排除。
- Committed source-bundle clean extraction：從 commit `792d29602a39ad96925edea8d208e2c4ccb7642d` 建立 82-file source ZIP，clean extraction 內 package/notebook import 與 pytest 全部 PASS，`107 passed`；ZIP 248,166 bytes，SHA-256 `13B7611172551171D6504D96477B4500E3F9526C4409332D2525077AA0F18B91`，位於 gitignored `artifacts/handoff/`。
- Full clean-checkout reproduction：以 `git archive` 從同一 commit 匯出全部 96 tracked files，確認 import 來自全新 extraction，Ruff check PASS、Ruff format check `63 files already formatted`、pytest `107 passed`（僅 2 個既知 legacy ONNX exporter deprecation warnings）。
- Hosted CI 未執行：本 repository 仍無 Git remote，且本次沒有 remote/push 授權；不為了關閉 M6 而擅自擴大外部發佈範圍。

### 2026-08-03 — c7 handoff-only recovery 修復

- Colab `7d69e7714a52` recovery evidence：FUSeg integrity 810／200／200 PASS；六組 final runs 的 ONNX parity、CPU benchmark 與五分類 private gallery 全部完成並寫入 private Drive。
- 原始失敗 U-Net seed 42 parity 已完成：`max_abs_logit_error=0.0003871917724609375`、`max_abs_probability_error=0.00008478760719299316`、mask mismatch 1 pixel／`0.000003814697265625`、material mismatch 0、`parity_passed=true`。
- 最後唯一失敗 stage：`safe_result_handoff`；root cause 是 result-bundle privacy regex 將正常 `https://github.com/...` URL 中的 `s:/` 誤判為 Windows drive path，不是 Drive 目錄、training、checkpoint 或 ONNX failure。
- TDD regression：HTTPS URL acceptance 先 RED；hash-valid completed ONNX across repair commits handoff-only resume 先 RED；UNC／extended UNC privacy rejection 先 RED，修復後全部 GREEN。
- Recovery contract：先 hash 驗證 `locked_loss_selection`、`multi_seed_final`、`official_validation` 與 completed `onnx_and_benchmark`；驗證通過時只執行 `safe_result_handoff`，不下載資料、不重做 ONNX/benchmark/gallery、不重跑 training。
- `.venv\Scripts\python.exe -m ruff check .`、`ruff format --check .`、`pytest -q`、`git diff --check` → PASS；107 tests passed，只有 2 個既有 legacy ONNX exporter deprecation warnings。
- 獨立 code review：UNC privacy gap 修復後無 Critical／Important findings；ready to merge；focused 22 tests PASS。
- Clean-extracted source bundle gate：107 tests PASS；source ZIP inventory 82 files；training provenance 維持 `c7ec6060f1bd0a813a890b95b50c2855d3c2640c`，repair implementation 由 bundle manifest 獨立記錄。
- GPU/full training：未在本機執行；無 remote、push、公開 upload 或 weights/data handoff。

### 2026-08-03 — M1 locked `exclude_train` gate

- Git baseline：`main@540063b`、clean tracked worktree、author `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`、0 remotes；已建立 `portfolio/woundscope-colab-full-run`。
- `.venv\Scripts\python.exe -m pytest -q`（變更前 baseline）→ PASS；50 passed、2 個既有 legacy ONNX exporter deprecation warnings。
- `.venv\Scripts\python.exe -m pytest tests\test_protocol_reporting.py tests\test_data_integrity.py -q` → PASS；12 passed。
- `.venv\Scripts\python.exe scripts\download_data.py --skip-download --allow-cross-split-exact` → structural PASS；train 810／validation 200／test 200，masks 810／200／0，structural issues 0，維持 anti-alias warning 與 pHash warning reporting。
- `validate_exclude_train_contract(... expected_exclusion_count=7, expected_validation_count=200, split_seed=42)` → `M1_POLICY_GATE_PASS`；只排除 7 張 official-train copies、official validation 200 張完整保留、retained train/dev duplicate-group isolation PASS。
- 科學決策：`exclude_train` 已由使用者明確批准並寫入 `PROJECT_PLAN.md` Decision Log；允許產生 duplicate report 不授權 contaminated training。
- GPU/full training：未執行；本機 RTX 4090 未使用；remote/push/upload 未執行。

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

- Working directory：repository root。
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
| `PROJECT_PLAN.md` | Active contract | Review gate 已解除；exact-duplicate mitigation 已鎖定為 `exclude_train` |
| `PROGRESS.md` | Active | 即時進度、證據與續作入口 |
| `.env` | Preserved and ignored | 內容未讀出、未修改、未追蹤 |
| M0 source/config/tests | Created and verified | Package、YAML config、CLI、AGENTS、skill、license 與 ignore rules |
| `data/raw/fuseg/` | Local, gitignored | Pinned official sparse checkout；不可 commit／重傳 |
| `data/manifests/` | Local, gitignored | `data_manifest.csv`、`data_summary.json` 與 duplicate findings |
| M2–M5 source/tests | Created and CPU verified | data/model/loss/train/evaluate/calibration/ONNX/inference/Gradio stack |
| `notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb` | Thin staged wrapper, structure verified | 優先使用 private Drive immutable source ZIP；缺少 ZIP 時 checkout public `v0.1.0`；CUDA hard gate、single Run-all orchestration、Drive persistence／resume |
| `artifacts/handoff/WoundScope_colab_source.zip` | Local, gitignored; verified recovery bundle | Source `8345176593e3`、82 files、SHA-256 `773E0274487F54D040F68943A610BF53C97393157A49A5B50BA05A2B76537A8E`；clean-extract suite 107 passed |
| `artifacts/handoff/WoundScope_colab_source_792d296.zip` | Local, gitignored; final clean-source audit | Source `792d29602a39`、82 files、248,166 bytes、SHA-256 `13B7611172551171D6504D96477B4500E3F9526C4409332D2525077AA0F18B91`；clean-extract suite 107 passed |
| Release files | Created and verified | README/cards/CFF/CI/Docker/.env.example、`SECURITY.md`、issue form、aggregate SVG、v0.1.0 notes 與 artifact handoff |
| Model/training artifacts | Private Drive + verified safe local summary | 完整 checkpoints/ONNX/gallery 留在 private Drive；gitignored safe result evidence 52 members，不含 weights/images |

## Blockers and risks

### Active blocker

- 無未決科學決策、實驗或本機 gate blocker；v0.1.0 只剩 hosted CI、tag、GitHub Release 與 branch protection 等外部發布步驟。

### Known risks

- FUSeg challenge design 只寫「CC BY NC」，缺少版本與完整 legal text；禁止預設 data／weights 可再散布。
- 無 patient ID，無法建立 patient-wise split，可能存在 source/patient correlation。
- Official test masks 未公開，不能宣稱 test-set quantitative performance。
- Exact duplicate 與 pHash near-duplicate 可能高估 generalization；pHash distance 0 不等同 exact bytes 或相同 patient。
- 本機可能有其他工作負載；full training 預設只在 Colab 執行。

## Next actions

1. 維護 GitHub hosted CI、dependency pin 與 security updates；任何變更都需保留 Ruff／format／pytest／privacy audit gates。
2. Contributors policy 維持只有 `kuotunyu`；未來 commits 不得加入 bot、placeholder 或共同作者 trailer。
3. 保留 private Drive 的 checkpoints／ONNX 作為未公開備份；不得公開 weights、FUSeg 衍生影像或 image-level artifacts。
4. 只有新增實質功能、資料 protocol 或正式實驗時才建立下一個 milestone，並先更新 `PROJECT_PLAN.md`。

## Session log

### 2026-08-03 — Recovery dependency closure 與 preflight diagnostics

**實際 Colab evidence**

- Recovery source `22b80a3c4399` 在任何 data restore／ONNX command 前 exit 1；capture diagnostic 顯示：`Postprocessing recovery refused: upstream stage full_comparison is not hash-valid and completed`。
- A100／CUDA gate 已通過。這次沒有重跑 training，也沒有產生新的模型結果。

**根因與修正**

- 舊 recovery 對 quick 至 official validation 的每個 stage 做全 inventory hash gate；但 final ONNX／handoff 並不依賴 quick smoke 或未入選的 full-comparison ablations，因此非必要檔案也能錯誤阻擋 recovery。
- Required dependency closure 改為 `locked_loss_selection`、`multi_seed_final`、`official_validation`。`multi_seed_final` 仍涵蓋六個 selected final runs，包括重用的 seed-42 checkpoint／calibration／config／provenance／history；任何必要檔遺失、size 或 SHA-256 不符仍立即停止，且不呼叫 training handler。
- Preflight error 現在列出具體 missing／size／SHA-256 mismatch path；notebook 使用 streamed combined stdout/stderr 並在外層例外保留最後 100 行，不再只顯示 exit code。

**目前驗證**

- RED：刪除 synthetic quick/full-comparison markers 後，舊 recovery 分別在 `quick_gpu_gate`／`full_comparison` 拒絕。
- GREEN：同一情境只執行 `data_integrity`、`onnx_and_benchmark`、`safe_result_handoff`；training handlers 呼叫數為 0。
- Pipeline + recovery notebook focused suite → 16 passed；獨立 review 確認 dependency closure 仍涵蓋六個 final runs 與 official artifacts、沒有 training fallback，最終 no findings。
- `.venv\Scripts\python.exe -m ruff check .`、`ruff format --check .`、`pytest -q`、`git diff --check` → PASS；101 tests passed，2 個既有 legacy ONNX exporter deprecation warnings。
- Fix commit `7d69e7714a52dd44466ad729cd9338032bf66cc0` source ZIP：82 files、246,833 bytes、SHA-256 `D8B906256FBF146DC328671E7967EE280F5916BB89521C6A4EDF0804AA0F6296`。
- Source manifest／inventory／size／SHA-256／clean extraction → PASS；clean extracted source 完整 suite → 101 passed、2 個既有 legacy ONNX exporter deprecation warnings。

### 2026-08-03 — c7ec606 ONNX parity 與 postprocessing-only recovery

**目標**

- 修正已完成長時間 training／official validation 後，第一個 ONNX export 因浮點層級差異才在倒數第二 stage 失敗的問題。
- 保留 Drive 的 `WoundScopeArtifacts/c7ec6060f1bd/`，只恢復資料並重跑 ONNX／benchmark／gallery／safe handoff，禁止自動退回訓練。

**Colab evidence 與根因**

- `c7ec6060f1bd` pipeline 已進入 `onnx_and_benchmark`；依固定 stage order，quick、full comparison、locked loss selection、multi-seed final 與 official validation 已完成並持久化。尚未回收 safe result bundle，因此不在文件中抄錄或宣稱任何模型 metrics。
- 第一個 U-Net seed-42 export 產生有效 ONNX，但 legacy gate 回報 logit `max_abs_error=0.0003871918`、`rtol=0.001`、`atol=0.0001`、exact masks unequal。Sigmoid 的 Lipschitz bound 使相應最大 probability drift 不超過約 `0.0000968`；舊 gate 直接以 logit allclose + exact threshold equality 判斷，會把 threshold 附近的 backend rounding 視為 material failure。

**決策與變更**

- `PROJECT_PLAN.md` 已鎖定部署層 parity：raw model probabilities 維持 `rtol=1e-3`／`atol=1e-4`；temperature-calibrated threshold 轉成代數等價的 raw decision threshold，mask disagreement 只有在兩端皆位於該 threshold 的 `atol` band、且同時不超過 32 pixels／`1e-4` fraction 才可通過。Exact masks、logit allclose、最大 logit/probability error、mismatch count/fraction 均保留為 machine-readable diagnostics。
- 新增 postprocessing-only resume entry point。啟動前逐一驗證 quick 至 official validation 的 completed status、size 與 SHA-256；任一 upstream artifact 不完整即停止，絕不呼叫 training handler。
- 新增綁定原始 training source `c7ec6060f1bd0a813a890b95b50c2855d3c2640c` 的 recovery notebook；result bundle primary provenance 維持原 training source，另記錄執行修復的 `implementation_source_commit`。

**目前驗證**

- Probability／threshold-band parity 正例與 material-drift 反例 regression：PASS。
- Postprocessing-only resume 與 upstream artifact tamper/absence refusal regression：PASS。
- Notebook pinning／CLI manifest binding／相關 ONNX、pipeline、release suite → 31 passed，2 個既有 legacy ONNX exporter deprecation warnings。
- `.venv\Scripts\python.exe -m ruff check .`、`ruff format --check .`、`pytest -q`、`git diff --check` → PASS；101 tests passed，2 個既有 legacy ONNX exporter deprecation warnings。
- 獨立 code review 的 mask-drift ceiling、CLI manifest binding、stale retry diagnostics 三項 findings 均已修正並 re-review；最終 no findings。
- 修復 commit `22b80a3c43990d0efad02dcee4e0ef5cbe61932e` 建立 source ZIP：82 files、246,096 bytes、SHA-256 `D14D29BC12A513D0EAD002443AABCDD7F0D02D956E9B7621AAC7D2B8E2DF09D2`。
- Source ZIP manifest／inventory／size／SHA-256 驗證與 clean extraction → PASS；在 clean extracted source 重跑完整 suite → 101 passed、2 個既有 legacy ONNX exporter deprecation warnings。

**Artifacts**

- `notebooks/WoundScope_FUSeg_c7ec606_Postprocess_Resume_Colab.ipynb`
- `scripts/resume_colab_postprocessing.py`
- `artifacts/handoff/WoundScope_colab_source.zip`（source `22b80a3c4399`，已 clean-extract 驗證）

### 2026-08-03 — SegFormer-B0 checkpoint evaluation architecture 修正

**目標**

- 修正 A100 quick gate 載入 SegFormer-B0 checkpoint 時，evaluation model 被錯建為 tiny test architecture 的 state-dict shape mismatch。

**根因與變更**

- Training 使用 `build_model(..., pretrained=True)`，建立正式 `nvidia/mit-b0`（hidden sizes 32/64/160/256、decoder 256）。
- Evaluation/export 使用 `build_model(..., pretrained=False)` 以避免重載 pretrained weights；舊實作卻把所有 non-pretrained SegFormer 都建成 CI tiny variant（8/16/32/64、decoder 32），因此正式 checkpoint 無法載入。
- Model config 現在明確鎖定 `variant: b0`；non-pretrained evaluation/export 會依明列的 B0 shape fields 建立無預訓練權重但架構相同的模型。缺少 variant 時安全預設為 B0，只有測試 fixture 明確指定 `variant: tiny` 時才使用 tiny model。
- 不變更模型 family、loss、資料 split、訓練 protocol 或 checkpoint schema。

**Colab evidence**

- Source `0425c787cb1c` 已通過先前的 inference-tensor calibration 問題，並到達 `quick_segformer_b0_bce_dice_seed42` dev evaluation。
- 失敗 checkpoint tensors 為正式 B0 shapes，evaluation tensors 為 tiny shapes；詳細 mismatch tail 已由 pipeline diagnostic 保存。尚無可宣稱的 quick/full metrics。

**驗證**

- 正式 checkpoint／non-pretrained evaluation architecture regression：RED 重現相同 state-dict mismatch；GREEN → 1 passed。
- Model/config focused suite → 12 passed。
- 實際 `nvidia/mit-b0` pretrained training model → non-pretrained B0 evaluation model strict state-dict load → `SEGFORMER_B0_CHECKPOINT_COMPATIBILITY_PASS`；兩者皆 3,714,401 parameters。
- Missing-variant production-default regression：RED（118,225 tiny parameters）→ GREEN（3,714,401 B0 parameters）。
- `.venv\Scripts\python.exe -m ruff check .`、`ruff format --check .`、`pytest -q`、`git diff --check` → PASS；90 tests passed，2 個既有 ONNX exporter deprecation warnings。
- Clean-source bundle verification 待本次修正 commit 後執行。

**Artifacts**

- `configs/models/segformer_b0.yaml`
- `src/woundscope/models.py`
- `tests/test_models.py`
- `artifacts/handoff/WoundScope_colab_source.zip`（需從本次 clean fix commit 重建）

### 2026-08-03 — Colab temperature calibration inference-tensor 修正

**目標**

- 修正 A100 quick evaluation 在 dev-only temperature calibration 進入 LBFGS 時的 PyTorch runtime error。

**根因與變更**

- `collect_tta_logits` 正確使用 `torch.inference_mode()` 收集 logits/targets；但 `fit_temperature` 原本只做 `detach().float().cpu()`。當 tensor 已在 CPU/float32 時，這些操作可保留 inference-tensor 身分，LBFGS autograd 嘗試保存 `logits / temperature` 時即失敗。
- 在 calibration/autograd boundary 明確 `clone()` logits 與 targets，轉成一般 tensor 後才執行 temperature optimization；不變更模型、loss、資料 split 或評估 protocol。
- 新增 regression test，直接將 `torch.inference_mode()` 建立的 logits/targets 傳入真實 `fit_temperature`，修正前重現相同 RuntimeError，修正後通過。

**Colab evidence**

- `quick_gpu_gate` 已進入第一個 U-Net/BCE+Dice run 的 dev evaluation，checkpoint 與 calibration output path 已建立；失敗發生於 temperature fitting，尚無可宣稱的 quick/full metrics。
- 舊版 `c3c98c2ad3bb` 的詳細 subprocess tail 成功保存真正 root cause，證明 diagnostic fix 生效。

**驗證**

- Inference-tensor calibration regression：RED 重現相同錯誤；GREEN → 1 passed。
- Calibration/uncertainty focused suite → 7 passed。
- `.venv\Scripts\python.exe -m ruff check .`、`ruff format --check .`、`pytest -q`、`git diff --check` → PASS；88 tests passed，2 個既有 ONNX exporter deprecation warnings。
- Clean-source bundle verification 待本次修正 commit 後執行。

**Artifacts**

- `src/woundscope/calibration.py`
- `tests/test_calibration_uncertainty.py`
- `artifacts/handoff/WoundScope_colab_source.zip`（需從本次 clean fix commit 重建）

### 2026-08-03 — Colab Drive／resume／diagnostic 修正

**目標**

- 修正實際 Colab 首跑暴露的 Drive 路徑與可恢復性缺陷，並讓下一次失敗能保留真正的 stage/child process 診斷。

**觀察與變更**

- 舊 notebook 錯誤尋找 `MyDrive/WoundScope_colab_source.zip`；實際 private project 位於 `MyDrive/WoundScope/`，已改為零手動編輯的固定 project path。
- 首次 A100 run 已完成 Drive mount、source verify/extract、dependency/CUDA gate，pipeline 約兩分鐘後 exit 1；舊 executor 只留下外層 `CalledProcessError`，已關閉的 runtime 無法回推出未保存的 child traceback，因此不臆測內層原因。
- 每個 source commit 改用獨立 `WoundScopeArtifacts/<source-commit-prefix>/`，避免新 bundle 與舊 `pipeline_state.json` 衝突。
- Colab `/content/woundscope_data` 是暫存資料；每次啟動 pipeline 都會重新執行 idempotent `data_integrity` 下載/驗證資料，再從 Drive trainer state 繼續或略過已驗證的後續 stages。
- stage subprocess 現在即時串流 combined stdout/stderr，並將最後 80 行寫進 failed stage state；notebook 會直接回報失敗 stage、error type 與診斷內容。
- bundle manifest 的 source commit 必須是 40 位小寫 hexadecimal Git SHA，且在任何 project/artifact path 建立前驗證。

**驗證**

- Notebook project-path executable regression、volatile-data resume regression、subprocess diagnostic regression → PASS。
- Targeted Colab pipeline/notebook suite → 11 passed。
- `.venv\Scripts\python.exe -m ruff check .`、`ruff format --check .`、`pytest -q`、`git diff --check` → PASS；87 tests passed，2 個既有 ONNX exporter deprecation warnings。
- Production `data_integrity` handler 使用本機 pinned FUSeg 驗證 → PASS；810/200/200 scale 與 augmentation grid 正常。
- Deliberate-stop quick CPU resume boundary → PASS；正式 U-Net EfficientNet-B0 與 SegFormer-B0 model construction → PASS。
- 尚未宣稱 Colab quick/full、locked validation 或模型結果成功；需用修正版 immutable bundle 重跑。

**Artifacts**

- `notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb`
- `artifacts/handoff/WoundScope_colab_source.zip`（需在 clean fix commit 後重建）

### 2026-08-03 — 可恢復 staged Colab orchestration

**目標**

- 將 manual quick／comparison／final notebook 改為一次啟動、可恢復、可驗證與 privacy-safe 的八-stage pipeline。

**變更**

- 新增固定 experiment matrix、internal-dev-only loss selection、四層 tie-break、seed-42 hash/provenance reuse gate 與 atomic stage state。
- Quick mode 使用同一 config 先在第 1 epoch deliberate stop，再由 trainer state 實際 resume；結果記錄 `resume_verified`、`resumed_from_epoch` 與 `amp_enabled`。
- 新增 CUDA-only default handlers，串接 integrity、augmentation、quick、comparison、selection、final、official validation、ONNX/parity/benchmark、private deterministic gallery 與 safe handoff。
- 新增三-seed official-validation recomputation、image-cluster bootstrap、TTA confidence aggregate、source-commit provenance fallback，以及防手抄／tamper 的 README aggregate guardrail。
- 新增 committed allowlist source ZIP與 curated results ZIP builders；驗證 path safety、exact inventory、size/SHA-256、schema、source commit、secret/absolute-path/private-artifact rejection。
- Notebook 縮為 mount／source verification／install+CUDA gate／單一 staged command 五個 cells；更新 safe result 下載與驗證說明。

**驗證**

- `.venv\Scripts\python.exe -m ruff check .` → PASS。
- `.venv\Scripts\python.exe -m ruff format --check .` → PASS；62 files formatted。
- `.venv\Scripts\python.exe -m pytest -q` → PASS；82 passed，2 個既有 legacy ONNX exporter deprecation warnings。
- Hard-coded platform path scan PASS；manual `RUN_MODE`／`FULL_STAGE`／selected-loss switch scan PASS。
- Self-review regression：所有 CUDA training（quick/full）強制 `amp_enabled=true`；official aggregate 強制 calibration `source_split=dev`；safe bootstrap distribution 可在本機重算 2,000-sample percentile CI並拒絕 tamper。
- `.venv\Scripts\python.exe -m pytest tests\test_training_vertical.py tests\test_notebook_release.py -q` → PASS；4 passed，包含 actual compatible resume 與 thin-notebook structure。
- Mypy：`pyproject.toml` 未配置，依規格記錄為 `NOT_CONFIGURED`，未假裝執行。
- Ignore gate：`.env`、data/manifests、artifacts、weights、ONNX、generated/gallery paths 全部命中 `.gitignore`。
- Tracked privacy audit：除允許的 `data/.gitkeep`／`data/README.md` 外，無 tracked data、image-level manifest、醫療影像、masks、weights、ONNX、TensorBoard、sample predictions 或 error gallery。
- Secret-like assigned-value filename audit PASS；`GIT_REMOTE_COUNT=0`。
- `reports/generated/augmentation_preflight.png`（gitignored）實際 visual inspection PASS：image/mask alignment 一致，horizontal flip／rotation 同步，brightness/color mild；無 vertical flip、強 crop 或 mask drift。SHA-256 `011D40E6D3CA5D9834EDE6F9C6584BFD634617D36F8A80F5682F3F0AB6F3E637`。
- 本機 RTX 4090／full local training：未使用／未執行。

**Artifacts**

- 新增 `src/woundscope/orchestration.py`、`colab_pipeline.py`、`results.py`、`bundles.py` 與三個 thin scripts。
- `reports/generated/augmentation_preflight.png`（gitignored private visual evidence）。
- 舊 `artifacts/handoff/WoundScope_colab_source.zip` 保留但標記為 obsolete；尚未以未 commit 工作樹打包。

**決策／偏差**

- 無 scientific protocol 偏差；official validation 只會在 selection、final configs、checkpoints 與 dev calibration 全部凍結後執行。
- M3 仍未 Completed：缺少真實 Colab CUDA quick/full evidence。

**未完成與下一步**

- 建立 pre-Colab feature commit，從 clean HEAD 重建並 clean-extract 驗證 source ZIP，再進入 Colab GPU gate。

### 2026-08-03 — 鎖定 exact-duplicate mitigation

**目標**

- 將使用者已批准的 `exclude_train` 決策落地並重跑 M1 scientific gate。

**變更**

- 新增正式 contract verifier，驗證排除項目全為 train、official validation 完整保留、retained internal train/dev duplicate-group isolation。
- 更新 `PROJECT_PLAN.md`、README、DATA_CARD、MODEL_CARD 與本文件，移除過時的未決決策文字。

**驗證**

- Official data 810/200/200、masks 810/200/0、structural issues 0。
- 7 train copies excluded、validation 200 retained、split seed 42、duplicate-group isolation PASS。
- Protocol/data focused tests：12 passed。

**Artifacts**

- `data/manifests/data_manifest.csv`、`data/manifests/data_summary.json`（gitignored；未追蹤）。

**決策／偏差**

- `exclude_train` 已 Locked；pHash findings 維持 warning，不宣稱 patient-wise split。

**未完成與下一步**

- 實作並驗證 staged Colab pipeline；尚未使用本機或 Colab GPU。

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
- `notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb`
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
