# Hugging Face Space 安全部署指引

> 狀態：`PERMISSION_PENDING`。本文件是部署前的人工程序契約；目前只允許建立、驗證與審閱 code-only candidate，**不得**建立 Space、建立 model repository、上傳檔案、使用 token 或啟用 live mode。只有在資料集維護者／權利人以可保存的方式明確同意後，才可依本指引執行後續步驟。

## 目前可做的 code-only 準備

在乾淨且已提交的 working tree 中，以下 PowerShell 指令只會在本機建立候選目錄與 ZIP，預設輸出為 `artifacts/huggingface-space/candidate/` 與 `artifacts/huggingface-space/WoundScope_hf_space_code_only.zip`：

```powershell
.venv\Scripts\python.exe scripts\build_huggingface_space_bundle.py
```

指令輸出的 JSON 必須為 `status: "verified"`。審閱 `bundle_manifest.json` 的 `source_commit`、每個檔案的 `size` 與 SHA-256，並記錄 ZIP 的 SHA-256；未通過驗證不得進入任何外部服務。

候選的**精確 inventory**以該 manifest 為準，且只能是 `README.md`（來源為 `deploy/huggingface/README.md`）、`.dockerignore`、`Dockerfile`、`LICENSE`、`pyproject.toml`、`uv.lock`、已提交的 `app/**/*.py` 與 `src/**/*.py`，加上產生的 `bundle_manifest.json`。任何未列在 manifest 的成員均為拒絕條件。

禁止 inventory 包含 `.env`、FUSeg images 或 labels、image-level manifest、gallery、sample prediction、checkpoint、ONNX、`.pt`、`.pth`、`.safetensors`，以及 `.bmp`、`.gif`、`.jpeg`、`.jpg`、`.png`、`.tif`、`.tiff`、`.webp`。建置器也會拒絕 secret-like 值與絕對路徑；不可為了通過檢查而放寬這些規則。

## 候選驗證順序

在 Docker 前後都必須使用同一份 exact verifier；import 使用 `python -B`，避免產生 `.pyc` 汙染候選目錄：

```powershell
$candidate = (Resolve-Path 'artifacts/huggingface-space/candidate').Path
$bundle = (Resolve-Path 'artifacts/huggingface-space/WoundScope_hf_space_code_only.zip').Path
$env:PYTHONPATH = (Resolve-Path (Join-Path $candidate 'src')).Path
.venv\Scripts\python.exe -B -c "from woundscope.gradio_app import build_demo; d=build_demo(); assert d.analytics_enabled is False; assert d.delete_cache==(600,600); print('HF_SPACE_IMPORT_SMOKE_PASS')"
.venv\Scripts\python.exe -B -c "import json; from pathlib import Path; from woundscope.bundles import verify_huggingface_space_candidate; d=Path(r'$candidate'); z=Path(r'$bundle'); m=json.loads((d/'bundle_manifest.json').read_text(encoding='utf-8')); verify_huggingface_space_candidate(d,z,expected_source_commit=m['source_commit']); print('HF_SPACE_POST_IMPORT_VERIFY_PASS')"
docker build -t woundscope:hf-space-code-only $candidate
.venv\Scripts\python.exe -B -c "import json; from pathlib import Path; from woundscope.bundles import verify_huggingface_space_candidate; d=Path(r'$candidate'); z=Path(r'$bundle'); m=json.loads((d/'bundle_manifest.json').read_text(encoding='utf-8')); verify_huggingface_space_candidate(d,z,expected_source_commit=m['source_commit']); print('HF_SPACE_POST_DOCKER_VERIFY_PASS')"
Remove-Item Env:PYTHONPATH
```

Challenge 文件雖出現「CC BY-NC」，但版本與正式 legal code 尚待 FUSeg rights holder 確認；在取得可保存的書面同意前，維持 `PERMISSION_PENDING`，不發布 derived weights、ONNX 或 live inference。

## 授權完成後才可選擇的可見性

| 選項 | 適用情況 | 本專案目前是否可啟用 live mode |
|---|---|---|
| Public Space | 權利人已明確書面同意公開衍生模型、ONNX 與 public non-commercial inference，且已確認 attribution 與其他限制。 | 不可；`PERMISSION_PENDING`。 |
| Protected Space | 權利人允許受控使用，且存取名單、保留期限與模型讀取權限均已核定。 | 不可；`PERMISSION_PENDING`。 |
| Private Space | 權利人只允許指定維護者使用，且 private storage 的衍生權重與存取控制已核定。 | 不可；`PERMISSION_PENDING`。 |

在權利範圍、可見性與 live mode 都獲明確同意以前，任何選項都不得實作或啟用。Apache-2.0 僅適用 WoundScope 自有程式碼，不能用來推論 FUSeg 或衍生 model artifacts 的權利。

## 模型存取與 secrets

模型後端只能使用 immutable `HF_MODEL_REVISION`；其值必須是 40-character 小寫 Git commit SHA。branch、tag、空值、短 SHA 或大寫 SHA 都必須 fail-closed，不得改以較寬鬆的 revision 繼續下載。model 與 calibration 必須使用同一個 revision，並在部署紀錄寫下 model hash。

待授權核定後，才可在人工核准的 publish session 中使用最小權限的 fine-grained write token；它只可用於該次發佈，結束後立即撤銷，不能寫入 repository、檔案、log、環境範例或 runtime secret。Space runtime 不得保有寫入 token。若已核准受保護／私有模型讀取，runtime 僅可設定最小權限的 read-only model access，且不得輸出 token 值、檔名或私有 artifact 路徑。

## 發佈前人工 checklist

下列每項均須有可追溯紀錄，且全數完成才可由獲授權人進行外部操作：

- [ ] 權利人已對 requested use、derived model weights、ONNX、attribution、可見性與 public non-commercial inference 做出明確書面答覆。
- [ ] owner 為 `kuotunyu`，並已選定與授權一致的 visibility、CPU Basic 與 port 7860。
- [ ] candidate 與 ZIP 均已驗證；manifest、ZIP SHA-256、model hash、`HF_MODEL_REVISION` 及 planned rollback commit 已記錄。
- [ ] Privacy copy、FUSeg attribution、非臨床用途／人工複核警示與不記錄影像內容的限制均已人工審閱。
- [ ] 已確認沒有資料、權重、ONNX、影像、私有 manifest 或 secret 會被上傳；所有 runtime variables 都是最小權限且不含 write token。

## Rollback、teardown 與暫存資料

若部署後發現權利、隱私、hash 或 manifest 問題，立即停止 live mode，回復到已驗證的前一個 Space commit（rollback），並保存原因、時間與 commit reference。若無可接受的已驗證 commit，執行 teardown：移除 Space、撤銷該次 publish token、移除 runtime secret 與模型存取權，再留下不含 secret 的稽核紀錄。這些動作只能由已取得外部操作授權的人執行。

Space 的暫存 cache 設為 10 分鐘是降低暴露窗口的控制，不是絕對刪除保證，也不是資料保留或隱私合規聲明。不得上傳或處理可識別健康資訊／PHI；使用者應只提供具備處理權限的非敏感影像，結果僅供研究與人工複核，不提供診斷、嚴重度、預後或治療建議。
