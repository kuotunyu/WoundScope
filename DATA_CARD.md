# WoundScope Data Card：FUSeg

## 摘要

WoundScope 使用 UWM Big Data Lab 公開的 Foot Ulcer Segmentation Challenge（FUSeg）資料，固定 repository revision `42a272dfe0679f20675e826385925cb7562934b6`。相關論文描述資料來自單一臨床來源、涵蓋數百位病患與多次 visits；公開 challenge 檔案未提供 patient ID，因此本專案無法重建 patient-level 關係。本 repository 只提供下載與驗證程式，不包含或重傳醫療影像、labels、image-level manifest 或衍生 gallery。

## 已驗證結構

| Split | Images | Masks | WoundScope 用途 |
|---|---:|---:|---|
| train | 810 | 810 | internal train/dev source |
| validation | 200 | 200 | locked final evaluation |
| test | 200 | 0 | blind inference smoke only |

驗證內容包括 image-mask pairing、解碼、尺寸、mask values、SHA-256 exact duplicate、pHash near-duplicate 與 cross-split findings。`validation/labels/0233.png` 含少量位於前景邊界的灰階 anti-alias pixels；pipeline 將其記錄為 warning，並以 threshold 128 正規化，未靜默忽略。

在 pinned revision 中發現 7 組 train–validation 完全相同影像。正式政策已鎖定為 `exclude_train`：排除 train 端 7 張 copies，完整保留 official validation 200 張；允許 duplicate report 產生不代表允許 contaminated training。Near-duplicate findings 是警告，不代表相同病人。

## Split protocol

資料沒有 patient ID，不可宣稱 patient-wise split。排除 7 張 exact train copies 後，官方 train 依 duplicate group 與 foreground-ratio bins，以 seed 42 建立約 80/20 duplicate-group-aware internal train/dev；官方 validation 不參與 checkpoint、loss、threshold、temperature 或 augmentation 選擇。官方 test 沒有公開 masks，不產生 quantitative metrics。

## 評估邊界

影像以保持比例的 longest-side resize 與 padding 轉為 512×512 後評估。Dice、IoU、precision、recall 與 specificity 均為此 resampled/padded 空間的分割指標；specificity 容易受大面積背景與 padding 主導。2,000 次 image-level Bootstrap 以影像為 cluster，未能處理未知的 patient-level correlation。

## 授權與允許用途

Challenge design PDF 的 data usage agreement 寫作「CC BY NC」，但沒有版本、正式 legal code 或 repository LICENSE。因此授權資訊視為不完整：

- 不 commit 或重新上傳 images、masks、manifest、predictions 或 error gallery。
- 不把 WoundScope Apache-2.0 LICENSE 解讀為涵蓋 FUSeg。
- 權重可能記憶資料特徵，公開到 GitHub／Hugging Face 前須人工確認原資料條款與非商業限制。
- 公開文件只放 aggregate statistics、產生方法與在條款允許下的 artifacts。

官方來源：[FUSeg challenge directory](https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge)、[challenge design PDF](https://github.com/uwm-bigdata/wound-segmentation/blob/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge/FootUlcerSegmentationChallenge2021.pdf)。

## 已知風險

- 缺少 patient、site、device 與 acquisition metadata，無法量化個案或來源相關性。
- 官方 split 存在 exact duplicates，near-duplicate 亦可能造成高估。
- 單一資料來源與未知 patient-level correlation 限制外部有效性；目前沒有多中心驗證。
- 未提供 demographic／skin-tone labels，無法完成 subgroup fairness audit。
- Foot-ulcer challenge 分布不能代表其他傷口類型或真實臨床工作流程。
- 原圖可能含敏感醫療內容；local/Drive artifacts 必須依使用者機構政策保護。

## 引用

Wang et al., “Fully automatic wound segmentation with deep convolutional neural networks,” *Scientific Reports* 10, 21897 (2020). https://doi.org/10.1038/s41598-020-78799-w
