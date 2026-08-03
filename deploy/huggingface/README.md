---
title: WoundScope
emoji: 🩹
colorFrom: blue
colorTo: teal
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: 足部潰瘍影像 segmentation 的研究與部署介面，不提供醫療診斷。
---

# WoundScope：足部潰瘍影像 segmentation 介面

> 狀態：`PERMISSION_PENDING`

本 Space 候選版僅含程式碼；目前沒有模型權重、ONNX 檔案、FUSeg 資料或任何病患相關資料。模型發布與下載設定必須先完成授權確認；未完成時，應維持 fail-closed 行為，不提供推論結果。

## 資料、權重與授權

- 不得上傳 FUSeg 原始影像、標註或病患相關資料。
- 不得將 checkpoint、ONNX、sample predictions、error gallery 或其他可辨識個案的產物加入此 Space。
- Apache-2.0 僅適用於 WoundScope 自有程式碼；FUSeg 的使用與歸屬應依官方資料使用條款辦理。
- 只有在權利與發布範圍經人工確認後，才能設定 `HF_MODEL_ID`、固定 `HF_MODEL_REVISION` 與模型檔名；不得使用 token、私密網址或未固定 revision 的模型來源。

## 使用範圍

這是研究與技術展示用途的 segmentation 介面。輸出僅為模型預測的像素區域、信心與人工複核提示；不提供疾病診斷、嚴重度、預後或治療建議。任何輸出都不應取代合格醫療專業人員的判斷。

## Space 建置

此候選目錄由 WoundScope repository 的受限 allowlist 產生。它使用 Docker 與 CPU ONNX 推論路徑；所有來源檔都會由 `bundle_manifest.json` 的檔案清單與 SHA-256 驗證。請只部署經驗證的 code-only ZIP，不要手動補入資料或模型檔案。
