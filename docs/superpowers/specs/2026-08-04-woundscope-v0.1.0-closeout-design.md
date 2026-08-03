# WoundScope v0.1.0 Closeout Design

## 目標

將已完成 M0–M6 的 WoundScope 整理成可由外部使用者理解、驗證與啟動的
`v0.1.0` 公開版本，同時維持既有 scientific protocol、privacy policy 與單一
GitHub contributor 約束。這次不重新訓練、不變更正式 metrics，也不公開 FUSeg
images／masks、image-level artifacts、checkpoints 或 ONNX weights。

## 已批准的發布身分與界線

- Citation 與 Python package author 使用 `kuotunyu`；不填寫未提供的 ORCID。
- 所有新 commit 的 author／committer 固定為
  `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`。
- 不加入 `Co-authored-by`、`Signed-off-by`、`Reviewed-by` 或 bot-authored commits。
- README、GitHub Release、Description、About 與使用者介面以正體中文（`zh-TW`）為主，
  technical proper nouns 保留原文。
- 可公開既有 schema-valid privacy-safe result bundle 與 aggregate charts；不得公開
  data、weights、private galleries、sample predictions 或 image-level manifests。

## Public Colab entry point

現有 notebook 保留 private Drive source ZIP 的 immutable／resume workflow，並新增無需
預先上傳 ZIP 的 Public GitHub fallback：

1. 掛載使用者自己的 Google Drive，以保存 resumable artifacts。
2. 若 `MyDrive/WoundScope/WoundScope_colab_source.zip` 存在，沿用既有 manifest、inventory
   與 SHA-256 驗證流程。
3. 若 ZIP 不存在，從 `https://github.com/kuotunyu/WoundScope.git` checkout 固定的
   `v0.1.0` tag，取得 resolved 40-character commit SHA，並確認 checkout clean。
4. 兩種來源都輸出相同的 `project_dir` 與 `source_commit` 介面，後續 install、CUDA gate、
   staged pipeline、Drive artifact versioning 與 safe handoff 行為不變。
5. README Colab badge 直接開啟 GitHub `main` 上的 full-run notebook；README 明確說明
   Run all 會啟動完整 GPU pipeline，而非短 demo。

Public fallback 不下載任何 WoundScope model weight；FUSeg 仍由既有 pinned official-source
流程取得。Source tag 用於可重現的版本選擇，resolved commit SHA 仍寫入 provenance。

## Release evidence 與 aggregate visual

- 建立 annotated `v0.1.0` tag 與正體中文 GitHub Release。
- Release asset 使用已驗證檔案
  `woundscope_colab_results_c7ec6060f1bd.zip`，並在 release notes 記錄：
  - size `344656` bytes；
  - SHA-256 `6FF4D1F14F4242C72FA2EF3382BCBFADC15DF93DD4AEB739AE1864F7DE24F221`；
  - training source `c7ec6060f1bd0a813a890b95b50c2855d3c2640c`；
  - bundle 不含 data、weights、ONNX binaries、private images 或 image-level results。
- 新增 `reports/public/model_comparison.svg`，只呈現 schema-valid safe bundle 中的 locked
  official-validation aggregate Dice／IoU；圖上標示 `n=3 seeds` 與非 official-test、非
  clinical performance 的限制。README 結果區引用此圖。
- 圖表數值必須與 README marker table 及 verified bundle 完全一致；不得人工加入新結果。

## Metadata 與文件一致性

- `CITATION.cff`：author=`kuotunyu`、version=`0.1.0`、release date=`2026-08-04`，加入
  repository URL。
- `pyproject.toml`：author=`kuotunyu`，加入 Homepage／Repository／Issues URLs。
- `README.md`：修正 Colab URL、Public/Private source 說明、PowerShell environment syntax、
  frozen dependency sync、Release asset／chart 入口。
- `PROJECT_PLAN.md`：移除已完成後仍指向 Git initialization 的過期 next step，更新 citation
  與 Public Colab release contract；不改 scientific protocol。
- `PROGRESS.md`：新增 v0.1.0 closeout evidence，移除 current blocker 區的過期 M6 待辦，
  保留有日期的歷史失敗／修復紀錄。

## Repository security 與 contribution policy

- GitHub Actions 明確設定 `permissions: contents: read`，加入 `workflow_dispatch` 與同 branch
  concurrency cancellation；所有 action 繼續使用 full commit SHA pin。
- 新增正體中文 `SECURITY.md`，使用 GitHub private vulnerability reporting／Security Advisory
  作為聯絡入口，並重申本專案不是醫療器材。
- 新增 structured bug-report issue form；不得要求或鼓勵使用者上傳醫療影像、資料、權重或
  secrets。
- `main` branch 禁止 force push／delete，required status check 使用 `synthetic-gates`；owner
  保留 bypass，以避免 sole-maintainer repository 被鎖死。
- 不啟用會建立 bot commits 的自動 dependency update PR。Dependency/security alerts 由
  `kuotunyu` 人工處理並以 owner-authored commit 合併。

## Test strategy

所有 behavior change 採 TDD：

- Notebook tests 先證明 Public GitHub fallback、fixed tag、resolved SHA、clean checkout 與既有
  Drive ZIP flow 的共同 interface。
- Release metadata tests 驗證 Colab badge URL、CFF／pyproject author 與 URLs、CI minimum
  permissions、issue form 的 privacy copy，以及 SVG 數值與 README table 一致。
- Existing notebook execution tests 繼續以 synthetic Drive ZIP 覆蓋 private path，不進行
  network download或 GPU training。
- 完整 gate：Ruff、format、pytest、`git diff --check`、CFF parse、notebook JSON parse、local
  Markdown links、tracked privacy audit、default-history identity/trailer audit、clean-checkout
  reproduction。
- Push 後等待 hosted CI；只有 CI success、annotations=0、Contributors API 只列 `kuotunyu`、
  Release asset size/hash 正確且 branch protection 可讀回時，才完成 closeout。

## Failure handling

- Public clone 無法解析 `v0.1.0`、checkout dirty 或 SHA 格式錯誤時立即停止，不退回 `main`。
- Private ZIP 存在但驗證失敗時立即停止，不靜默改用 GitHub source。
- Safe result bundle 的 size、SHA-256 或 schema/privacy gate 任一不符時不建立／不發布 Release。
- Hosted CI 或 contributor audit 失敗時不宣稱 v0.1.0 closeout 完成；保留 release candidate
  狀態並修正後重驗。

## 明確不做

- 不重新執行 full training 或 official validation。
- 不發布 Hugging Face Space、weights 或 ONNX model asset。
- 不增加 official-test、patient-wise、外部、subgroup 或 clinical performance claims。
- 不加入 Mypy、coverage threshold、package registry publishing 或無關 refactor。
