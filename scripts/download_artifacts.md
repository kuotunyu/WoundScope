# 從 Google Drive 取回 WoundScope artifacts

Colab notebook 預設把每個 run 直接寫入 `MyDrive/WoundScopeArtifacts/runs/`，因此 runtime 中斷後 checkpoint、trainer state、CSV、TensorBoard 與 partial results 仍在 Drive。

## 建議步驟：Drive for desktop 或瀏覽器下載

1. 在 Google Drive 將完成的單一 `runs/<RUN_ID>/` 資料夾下載成 ZIP；不要下載或分享 `data/`。
2. 把 ZIP 放到 Windows 專案的 `artifacts/incoming/`（此路徑已被 Git ignore）。
3. 在 WSL2 進入 repository，解壓並驗證：

```bash
mkdir -p artifacts/runs
unzip /mnt/c/path/to/RUN_ID.zip -d artifacts/runs/RUN_ID
sha256sum artifacts/runs/RUN_ID/best_model.safetensors \
          artifacts/runs/RUN_ID/model.onnx
cat artifacts/runs/RUN_ID/provenance.json
```

4. 執行本機 CPU smoke：

```bash
.venv/bin/python scripts/predict.py \
  --model artifacts/runs/RUN_ID/model.onnx \
  --calibration artifacts/runs/RUN_ID/calibration.json \
  --input /path/to/local/image.jpg \
  --output artifacts/runs/RUN_ID/local_smoke \
  --device cpu
```

若要用 `rclone`，請自行在互動環境完成 Google Drive OAuth；不要把 token、Drive credentials 或 `.env` 放進 repository。模型權重在 FUSeg 授權未人工確認前只留在 private Drive／本機。
