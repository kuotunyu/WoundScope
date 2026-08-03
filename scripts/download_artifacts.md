# 從 Google Drive 取回 WoundScope safe handoff

Colab staged pipeline 將大型／private artifacts 保留在
`MyDrive/WoundScope/WoundScopeArtifacts/<source-commit-prefix>/`，最後只建立一份可回收的 aggregate bundle：

```text
MyDrive/WoundScope/WoundScopeArtifacts/<source-commit-prefix>/handoff/woundscope_colab_results_<source-commit-prefix>.zip
```

## 一次下載與驗證

1. 只下載上述 `woundscope_colab_results_*.zip`；不要下載或分享 `runs/`、data、weights、ONNX、TensorBoard、sample predictions 或 error galleries。
2. 將 ZIP 放入 Windows repository 的 `artifacts/incoming/`（已 gitignored）。
3. 在 repository 以 pre-Colab source commit 驗證並解壓：

```powershell
$resultBundle = (Get-ChildItem artifacts\incoming\woundscope_colab_results_*.zip |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1).FullName
$sourceCommit = git rev-parse HEAD
.\.venv\Scripts\python.exe scripts\verify_results_bundle.py `
  --bundle $resultBundle `
  --expected-source-commit $sourceCommit `
  --output artifacts\verified
```

驗證器會拒絕 path traversal、未列入 inventory 的 member、size／SHA-256 不符、source commit 不符、weights／ONNX／checkpoint／TensorBoard、image-level metrics、sample predictions、gallery、secret-like content 或 Drive absolute paths。只有通過 schema 與三-seed recomputation guardrail 的 `aggregate/verified_results.json` 才能用於 README 更新。

Private Drive 內的 checkpoints／ONNX 可用於授權允許範圍內的本機研究，但不屬於 safe handoff，也不得因本流程而公開或追蹤。
