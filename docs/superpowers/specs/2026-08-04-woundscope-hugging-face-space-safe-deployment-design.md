# WoundScope Hugging Face Space 安全部署設計

## 狀態與目標

本設計已於 2026-08-04 經使用者確認，目標是在**不公開 FUSeg data、trained
weights、ONNX、medical images、image-level artifacts 或 secrets**的前提下，先完成一套
可重現、可稽核、以正體中文（`zh-TW`）為主的 Hugging Face Space 純程式碼部署包。

目前階段固定為 `PERMISSION_PENDING`。程式碼準備完成不等於授權完成，也不等於 Space
已發布；只有資料權利人提供可保存的書面答覆後，才能另行評估 model artifact 的儲存方式與
public inference 範圍。

## 已批准的界線

- GitHub repository、README、部署文件與 Space 說明以正體中文為主，technical proper nouns
  保留原文。
- 所有 Git commit 的 author／committer 維持
  `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`；不得加入共同作者或 bot commit。
- 本階段不建立 Hugging Face Space、不操作 Hugging Face token、不發送授權詢問信，也不
  push 任何 Hugging Face repository。
- 不將 FUSeg images／masks、image-level manifests、private galleries、sample predictions、
  checkpoints、`.safetensors`、`.pt`、`.pth`、ONNX 或 calibration artifacts 放入部署包。
- 不改變既有 scientific protocol、official-validation results、medical scope 或 `v0.1.0`
  release。
- UI 只提供研究用途的 wound segmentation，不提供 diagnosis、severity、prognosis 或
  treatment advice。

## 方案選擇

### 採用：可重現的純程式碼部署包產生器

在 WoundScope repository 中維護 Hugging Face 專用 template 與 allowlist builder，輸出到
gitignored staging directory。部署包由目前 Git source 建立，包含 source commit、檔案清單、
size 與 SHA-256，並在完成前執行 prohibited-artifact audit。

此方案將 GitHub source、Hugging Face metadata 與未來 model delivery contract 分離，可避免
手動複製漏檔或意外夾帶 private artifact，也能讓每次部署候選版本被重新產生及驗證。

### 未採用：直接把 GitHub repository root 當 Space repository

這個方案步驟較少，但容易讓 Space-specific metadata 汙染主 repository，也增加日後 mirror
時誤帶 data／weights／release-only files 的風險；部署 inventory 亦不夠明確。

### 未採用：人工維護另一個 Space repository

短期最快，但會建立第二份容易漂移的 source、缺少 deterministic inventory，並提高人工上傳
private artifact、錯誤 commit 身分或遺漏 security copy 的機率。

## 系統構成

### 1. Space template

建立專用 template，至少包含：

- Hugging Face Space README front matter：`sdk: docker`、`app_port: 7860`，以及正體中文
  title／description／medical-use boundary。
- 使用現有 root `Dockerfile`、`app/app.py`、`src/woundscope/` 與必要的 package metadata；
  不複製開發、training、private data 或 experiment outputs。
- `PERMISSION_PENDING` 狀態與「目前不含可執行正式模型」的清楚提示。

Template 本身不得填入 account ID、token、model repository、private Drive path 或其他環境專屬
值。

### 2. Allowlist bundle builder

新增單一 CLI builder，從 repository root 的固定 allowlist 組合 Space candidate，預設輸出到
gitignored `artifacts/huggingface-space/`。Builder 必須：

1. 解析 repository root 與目前 Git commit，拒絕無法解析的 source。
2. 僅複製 allowlist 中的 regular files，不追蹤 symlink，不接受 path traversal 或絕對路徑。
3. 在乾淨 staging directory 建立候選檔案；既有非空目錄不得被靜默覆寫。
4. 掃描 filename、extension 與內容，拒絕 data、weights、ONNX、medical images、`.env`、
   secret-like assignments、token、private paths 及禁止的 generated artifacts。
5. 產生 machine-readable manifest，記錄 schema version、source commit、relative path、size
   與 SHA-256。
6. 依 stable path ordering 與 normalized ZIP metadata 產生 deterministic ZIP；相同 source
   與設定應得到相同 inventory 與 ZIP hash。
7. 驗證 ZIP clean extraction 後的 inventory 與 manifest 完全一致，成功才輸出 `verified`
   summary。

Builder 只建立本機 artifact，不包含 Hugging Face API、Git push 或 browser automation。

### 3. Gradio 隱私強化

現有 local demo 與未來 Space 共用同一個 `build_demo`，避免維護兩套 UI。預計變更：

- `analytics_enabled=False`，不主動送出 Gradio analytics。
- 設定短期 `delete_cache`，預設每 10 分鐘清除已超過 10 分鐘的 temporary files。
- Input source 限制為 explicit file upload，不啟用 webcam／clipboard。
- 移除會把內容分享到 Hugging Face Discussions 的 share control；output 亦不提供 public share。
- 若目前 Gradio API 支援，prediction event 設為 private API visibility，避免公開 API client
  入口；若不支援則 fail during tests，不以未驗證參數硬套。
- UI 顯示正體中文警語：只上傳使用者有權處理、且不含可識別個人資料的影像；禁止上傳
  Patient Health Information（PHI）。
- 不記錄原始 filename、image bytes、pixel summary 或 inference result；exception message
  只回報安全、可操作的失敗原因。

Existing segmentation、overlay、confidence 與 medical boundary 不變。Temporary-cache cleanup
降低殘留時間，但文件不得宣稱它等同絕對刪除保證。

### 4. Model artifact permission gate

部署程式沿用現有 local model path／`HF_MODEL_ID`／`HF_MODEL_REVISION` interface，但本階段
Space bundle 不設定任何正式 model source。

未來只有在書面授權回覆至少釐清下列事項後，才能提出下一份部署設計：

1. `CC BY-NC` 的精確版本與 legal code。
2. 以 FUSeg 訓練的 derived weights 是否可儲存於 private model repository。
3. Public、non-commercial inference 是否允許，以及是否需要額外 attribution／notice。
4. ONNX、PyTorch checkpoint 或其他轉換格式是否可再散布。
5. 對 user-uploaded inference、retention 與 downstream output 是否有額外限制。

授權詢問信只建立可供使用者審閱的草稿，不自動寄送。若回覆不完整或互相矛盾，狀態維持
`PERMISSION_PENDING`，不得猜測同意。

### 5. 文件與狀態呈現

新增正體中文部署指南與授權詢問草稿，說明：

- code-only candidate 的建立、驗證與解壓方式；
- candidate 明確包含與不包含的內容；
- 未來 Hugging Face secrets／variables 的最小權限原則；
- Public、Protected 與 Private Space 的差異與選擇條件；
- 發布前人工 gate，包括 owner、visibility、hardware、revision pin、privacy copy 與 rollback；
- teardown／rotation 流程，不在文件中放入任何實際 secret。

README 的 Hugging Face badge 維持「授權確認中」。只有 live Space 經 end-to-end verification
後，才可在另一個已批准變更中改成實際 URL。

## 資料與控制流程

```text
Git source commit
    │
    ├─ fixed allowlist ──> clean staging directory
    │                          │
    │                          ├─ prohibited-artifact audit
    │                          ├─ manifest + SHA-256
    │                          └─ deterministic ZIP + clean-extract verification
    │
    └─ Gradio privacy tests ──> code-only Space candidate

Written permission (future, separate approval)
    └─> model-delivery design ──> protected/private artifact ──> live Space verification
```

目前實作只到 `code-only Space candidate`；下半段不是本輪授權範圍。

## Failure handling

- Source commit、allowlist entry、symlink 或 path safety 不能驗證：立即停止，不產生 candidate。
- Staging directory 非空：拒絕覆寫，要求新的空白輸出位置。
- 發現禁止 extension、secret-like content、private path 或 manifest mismatch：刪除本次不完整
  staging candidate，保留不含敏感值的 error category。
- ZIP hash／clean extraction 不一致：標示 build failed，不保留 `verified` manifest。
- Gradio privacy control 無法由目前 pinned dependency 表達或測試：不降級成預設公開行為，
  阻擋 milestone gate。
- Model source 缺少、revision 未 pin 或 artifact hash 不符：UI 必須 fail closed，不改用任意
  public model。
- 沒有完整書面授權：不建立 live model-backed Space。

## Test strategy

Behavior change 採 TDD，至少覆蓋：

- Allowlist：合法 code-only candidate 通過；data、images、weights、ONNX、`.env`、token、
  absolute path、path traversal、symlink 與 unexpected file 逐一拒絕。
- Reproducibility：相同 source 連續建置得到相同 inventory、file hashes 與 ZIP hash；修改允許
  檔案後 hash 必須改變。
- Manifest：schema、source commit、stable ordering、size、SHA-256、ZIP inventory 與 clean
  extraction 全部一致。
- Gradio：analytics disabled、cache cleanup configured、upload-only、no public share、private
  event visibility、PHI warning 與 medical boundary 可由 config／component tree 驗證。
- Model gate：缺少或未 pin 的 model reference fail closed；現有 synthetic/no-model demo build
  smoke 不需要 GPU。
- Documentation：Space front matter、`PERMISSION_PENDING`、正體中文優先與禁止內容說明存在。
- Repository gate：Ruff、format、完整 pytest、`git diff --check`、tracked privacy audit、Git
  identity/trailer audit 與 clean-checkout reproduction。

本輪全部測試使用 CPU 與 synthetic fixtures；不下載 FUSeg、不重跑 training、不需要 GPU。

## Milestone 與交付物

建議將此工作記為 post-`v0.1.0` deployment-readiness milestone，完成條件如下：

1. 設計規格與 implementation plan 經使用者確認。
2. Allowlist builder、Space template、Gradio privacy hardening 與 tests 完成。
3. 正體中文 deployment guide 與 permission inquiry draft 完成。
4. 完整 local／clean-checkout gate PASS，並在 `PROGRESS.md` 記錄 exact evidence。
5. 只建立 `kuotunyu` author／committer 的 local commit；是否 push GitHub 另依使用者授權。

完成這個 milestone 後，WoundScope 會具備可安全交接的 code-only Space candidate，但狀態仍是
`PERMISSION_PENDING`，不宣稱已部署或可供正式醫療使用。

## 明確不做

- 不建立、修改或刪除任何 Hugging Face Space／model repository。
- 不要求、讀取、記錄或測試真實 Hugging Face token。
- 不上傳或重新包裝 model weights／ONNX／FUSeg-derived artifacts。
- 不寄出授權信、不代表權利人解釋授權，也不把 `CC BY-NC` 自行補成某個版本。
- 不使用 GPU、不重新 training／evaluation、不修改 verified metrics。
- 不修改 GitHub contributors policy、`v0.1.0` tag 或既有 Release。
