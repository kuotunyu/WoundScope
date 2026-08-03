# WoundScope 專案實作計畫

> 文件語言：正體中文（zh-TW）；medical computer vision、MLOps、程式符號與 CLI 名稱保留原文。  
> 文件角色：本文件是 WoundScope 的穩定規格與 implementation contract。即時進度、測試證據與下一步請見 `PROGRESS.md`。  
> 目前狀態：M0–M6 已完成；M1 cross-split mitigation 鎖定為 `exclude_train`，Colab 正式實驗、safe handoff、Public GitHub repository 與既有 hosted CI 均已完成；v0.1.0 tag／Release gate 的即時狀態請見 `PROGRESS.md`。Private data／weights／image-level artifacts 未公開。

## 1. 專案目標

WoundScope 是一套可重現、可測試、可部署的足部潰瘍影像分割作品，使用公開且已有 pixel-level annotation 的 Foot Ulcer Segmentation Challenge（FUSeg）資料。系統須涵蓋資料完整性檢查、PyTorch 訓練、統計評估、ONNX 匯出、Colab workflow、Gradio demo 與 release engineering，而不是只提供 notebook 草稿。

主要成功條件：

- 使用小型 ImageNet-pretrained U-Net baseline 與 SegFormer-B0 advanced model。
- 訓練預設可在 Colab T4 16 GB 執行，並將每個 epoch 的可恢復狀態持久化到 Google Drive。
- 本機 Windows 11／WSL2 可執行 evaluation、prediction、ONNX export、benchmark 與 Gradio demo。
- 所有正式結果都可追溯至 data revision、manifest、config、seed、environment 與 checkpoint hash。
- 不偽造 training result；full training 尚未完成時，公開結果表一律顯示「待填」。
- UI 只提供 segmentation output，不輸出疾病診斷、嚴重度或治療建議。

## 2. 已鎖定的界線

### 2.1 目前不做

- Pre-implementation review gate 通過前，不初始化 Git、不建立程式、不安裝依賴、不下載資料。
- 未經使用者明確授權時，不設定 Git remote，不推送 GitHub、Hugging Face 或其他外部服務。2026-08-04 已授權將程式碼公開至 `kuotunyu/WoundScope`；data、weights 與 private image artifacts 仍禁止上傳。
- 不在未取得明確授權確認前重新散布 FUSeg images、labels、含原圖的 gallery 或 trained weights。
- 不要求使用者自行標註，也不以檔名臆測 patient identity。
- 不在本機自動啟動 full training；訓練預設在 Colab，重型本機 GPU 工作需先確認。

### 2.2 變更控制

以下項目是 material decisions，修改前必須先討論、更新本文件的 Decision Log，再變更程式：

- data source、data revision、split policy 或 validation/test 的角色；
- model family、loss definition、正式 metrics 或 confidence／low-confidence 規則；
- medical output scope、公開資料／權重政策或 code license；
- artifact schema、正式結果產生流程或 release target。

一般 bug fix、測試補強與不改變 public behavior 的 refactor 可直接進行，但必須記錄在 `PROGRESS.md`。

## 3. 資料來源、引用與授權

### 3.1 官方來源

- Repository：<https://github.com/uwm-bigdata/wound-segmentation>
- 固定 revision：`42a272dfe0679f20675e826385925cb7562934b6`
- FUSeg 目錄：<https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge>
- Challenge design：<https://github.com/uwm-bigdata/wound-segmentation/blob/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge/FootUlcerSegmentationChallenge2021.pdf>
- 原始論文：Wang et al., *Fully automatic wound segmentation with deep convolutional neural networks*, Scientific Reports 10, 21897 (2020), <https://doi.org/10.1038/s41598-020-78799-w>

在上述 revision 已查證的目錄結構：

| Official split | Images | Masks | WoundScope 用途 |
|---|---:|---:|---|
| train | 810 | 810 | 建立 internal train/dev |
| validation | 200 | 200 | 鎖定的正式評估 |
| test | 200 | 0 | 盲推論與 challenge-format smoke test |

官方資料只提供影像與 masks，沒有可供 split 使用的 patient ID。因此不得聲稱 patient-wise split；同一來源、同一 patient 或同次 clinical workflow 的影像仍可能跨 split，必須在 DATA_CARD 與報告限制中明示 source correlation risk。

### 3.2 授權解讀與散布政策

Challenge design PDF 的 Data usage agreement 寫作「CC BY NC」，但未提供版本號、正式 legal-code link，官方 repository 根目錄也沒有 LICENSE。WoundScope 因此採保守政策：

- Apache-2.0 只涵蓋 WoundScope 自有程式碼。
- 原始 images、labels、image-level manifest、含原圖的 predictions/error gallery、checkpoints 與 ONNX weights 全部 gitignored。
- Repository 與 notebook 只提供官方下載流程，不重新上傳資料到 GitHub 或 Hugging Face。
- Model weights 預設只保存在本機／Google Drive；未經人工授權確認不得公開。
- 可公開 aggregate statistics、程式、synthetic fixtures、空白 templates 與不含原始病患影像的圖表。

## 4. 預定 Repository 結構

```text
.
├── .agents/skills/woundscope-development/
├── .github/workflows/
├── app/
├── configs/
│   ├── base.yaml
│   ├── models/
│   └── modes/
├── data/                       # gitignored raw/manifest content
├── notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb
├── reports/                    # tracked templates; generated/ is ignored
├── scripts/
├── src/woundscope/
├── tests/
├── AGENTS.md
├── CITATION.cff
├── DATA_CARD.md
├── Dockerfile
├── LICENSE
├── MODEL_CARD.md
├── PROJECT_PLAN.md
├── PROGRESS.md
├── README.md
└── pyproject.toml
```

核心 training、evaluation 與 inference 邏輯只存在 `src/woundscope`。Notebook 與 `scripts/` 只能組合與呼叫核心 API，不複製另一套 training implementation。

## 5. Reproducibility 與設定介面

- Python baseline：3.11；PyTorch 限定 2.x。
- Configuration：YAML deep merge，順序為 `base -> model -> mode -> CLI override`。
- Path：只使用 `pathlib`、config 與環境變數，不寫死 Windows、WSL、Drive 或 Colab absolute path。
- 主要環境變數：
  - `WOUNDSCOPE_DATA_DIR`
  - `WOUNDSCOPE_ARTIFACT_DIR`
  - `HF_MODEL_ID`（optional）
  - `HF_MODEL_REVISION`（optional）
  - `HF_TOKEN`（optional，不寫入 log）
- Device interface：`--device {auto,cpu,cuda}`。
- 固定 seeds：正式 multi-seed runs 使用 `42`、`43`、`44`；data split 使用 `42`。
- 啟用 PyTorch、NumPy 與 Python RNG seeding；deterministic algorithms 採 `warn_only`，並明示跨硬體不保證 bitwise identical。
- W&B 預設停用；必要紀錄使用 TensorBoard、CSV、JSON 與 provenance metadata。

## 6. Data pipeline

### 6.1 下載

`scripts/download_data.py` 使用 Git sparse-checkout，只取得固定 revision 的 `data/Foot Ulcer Segmentation Challenge`，預設目標由 config 或 `WOUNDSCOPE_DATA_DIR` 決定。流程須可安全重跑；若目標存在，先驗證 revision 與結構，不覆蓋不明資料。

### 6.2 Integrity validation

逐一驗證：

- train／validation image-mask stem pairing；test masks 缺少是預期狀態；
- Pillow decode／完整 pixel load，偵測損壞或截斷檔；
- image-mask width／height 一致；
- masks 僅包含 binary-compatible values，正規化為 `{0, 1}`；
- image 與 mask SHA-256 exact duplicate；
- image pHash near-duplicate 與 Hamming distance；
- within-split 與 cross-split duplicate findings；
- foreground pixel count、foreground ratio 與 empty-mask case。

結構性錯誤（unpaired、corrupt、size mismatch、invalid mask）使命令失敗。Exact cross-split duplicates 標為 high severity；允許產生 duplicate report 不等於允許 contaminated training。正式 training 固定採 `exclude_train`，只排除 train 端 exact copies；near-duplicates 只警告並寫入報告。

### 6.3 Manifest 與 split

Gitignored `data_manifest.csv` 至少包含：

```text
split,sample_id,image_relpath,mask_relpath,has_mask,
width,height,channels,mask_width,mask_height,mask_values,
foreground_pixels,foreground_ratio,image_sha256,mask_sha256,
image_phash,duplicate_group,validation_status,internal_split
```

Official train 先按 duplicate group 隔離，再依 foreground ratio quantile bins 分層，以 seed 42 建立約 80/20 internal train/dev。Official validation 不參與 early stopping、loss selection、threshold sweep 或 temperature scaling。Official test 不產生 quantitative metrics。

Pinned revision 已確認 7 組 official train–validation exact SHA-256 duplicate images。正式政策固定為 `exclude_train`：排除 train 端 7 張 copies，完整保留 official validation 200 張。pHash near-duplicate findings 維持 warning/reporting，不得據此聲稱 patient-wise split。

## 7. Models、Losses 與 Augmentation

### 7.1 Models

- Baseline：`segmentation-models-pytorch` U-Net，EfficientNet-B0 ImageNet encoder，單通道 logits。
- Advanced：Hugging Face Transformers SegFormer-B0 pretrained backbone，外部統一 upsample 至 target mask size，單通道 logits。
- CI／unit tests 不下載 pretrained weights，使用 `encoder_weights=None` 或 tiny local configuration。

### 7.2 Loss definitions

所有 loss 接受 raw logits 並處理 empty foreground：

```text
bce_dice = 0.5 * BCEWithLogits + 0.5 * DiceLoss(smooth=1e-6)
focal_tversky = 0.5 * Focal(alpha=0.75, gamma=2)
               + 0.5 * Tversky(alpha_fp=0.3, beta_fn=0.7, smooth=1e-6)
```

### 7.3 Augmentation

Training pipeline：

- resize／pad 到 512×512；
- optional mild random crop，必須保留至少 90% foreground，否則 retry／fallback；
- horizontal flip；
- rotation 限制 ±10°；
- 輕度 shift／scale；
- 小幅 brightness／contrast 與 color jitter；
- ImageNet-compatible normalization。

禁止 vertical flip、elastic／grid distortion、強烈 crop、coarse dropout、激烈 blur 或會改變 wound semantics 的 augmentation。每次正式訓練前輸出 original/image/mask 對照 grid 到 gitignored artifact directory，供人工 visual inspection。

## 8. Training protocol

### 8.1 Quick mode

- 每個 model/loss 使用固定 128 train、32 internal-dev samples。
- 2 epochs，seed 42，目標在常見 Colab T4 約 10–15 分鐘完成所有 smoke workflow。
- 只回報 internal-dev smoke metrics，不寫入正式 README 結果表。

### 8.2 Full mode

1. 以 seed 42 執行兩 models × 兩 losses 的 internal-dev ablation。
2. 每個 model 依 internal-dev mean image-level Dice 選定 loss；tie 時依序比較 global Dice、recall，再選較簡單的 BCE+Dice。
3. 選定配置執行 seeds 42、43、44；seed 42 的相同 ablation run 可重用，不重複訓練。

預設參數：max 50 epochs、batch size 8、gradient accumulation 2、AMP、AdamW、early-stopping patience 8、`min_delta=1e-4`。Checkpoint selection 使用 threshold 0.5 的 internal-dev mean image Dice；temperature 與 final threshold 在 checkpoint 凍結後才校準。

### 8.3 Resume 與 persistence

每個 epoch 以 temporary file + atomic replace 寫入 Google Drive／artifact directory：

- `last_model.safetensors`
- `trainer_state.pt`（epoch、optimizer、scheduler、GradScaler、early-stopping 與 RNG states）
- `history.csv`
- TensorBoard events
- `results.partial.json`

當 internal-dev criterion 改善時另寫 `best_model.safetensors`。Resume 必須驗證 config hash、model type 與 data-manifest hash 相容。

## 9. Evaluation、Calibration 與 Uncertainty

### 9.1 Metrics

每張影像保存 confusion counts 與以下 metrics：Dice、IoU、precision、recall、specificity。報告同時提供：

- per-image raw distribution；
- mean、median、standard deviation、IQR；
- global／micro metrics（聚合所有 pixels）；
- 每個 seed 的完整結果及三 seeds mean ± SD；
- 以 image 為 cluster、固定 bootstrap seed 的 2,000 次 percentile 95% CI。

Zero-denominator cases 必須採明確且測試覆蓋的規則；不得因 NaN 被靜默移除。

### 9.2 Threshold 與 calibration

- Temperature scaling 只在 internal dev 的 logits／labels 上 fitting。
- Threshold sweep 預設 0.10–0.90、step 0.02，選 internal-dev mean image Dice 最大值；tie 選最接近 0.5 者。
- Temperature、threshold、confidence cutoff 與 provenance 存入 `calibration.json`。
- Official validation 只能使用已凍結的 checkpoint 與 calibration artifact。

### 9.3 Confidence 與低信心

Inference 對原圖及 horizontal-flip view 各執行一次，將 flip prediction 還原後平均。Confidence 結合：

- candidate region 內 calibrated probability 的 normalized binary-entropy certainty；
- original 與 flipped prediction 的 soft／binary agreement。

Internal-dev confidence distribution 的第 10 百分位作為 cutoff。以下任一條件觸發「需人工複核」：

- confidence 低於 cutoff；
- predicted foreground 為空；
- calibration metadata 缺失或與 checkpoint 不相容；
- inference/preprocessing 發生可恢復但降低可信度的警告。

UI 必須標示「模型分割信心，非疾病或臨床信心」。

### 9.4 Error analysis

Local／Drive gallery 必須以 deterministic rules 選出：最佳、最差、小面積、低光與背景干擾案例。Gallery 不能只選漂亮結果，且其影像檔全部 gitignored。公開 README 只放 aggregate summary、生成指令與限制。

## 10. Colab notebook

`notebooks/WoundScope_FUSeg_FullRun_Colab.ipynb` 必須：

- 一鍵安裝 project dependencies、檢查 GPU／CUDA／Drive；
- 可從 mounted Drive project 或未來的 repository URL 讀取 WoundScope；
- 可從官方 pinned source 下載 FUSeg，或使用 Drive 既有資料；
- 執行 data validation、augmentation inspection、quick/full training；
- 支援 baseline、advanced、loss ablation、multi-seed final runs 與 resume；
- 每 epoch 將 best/last checkpoint、trainer state、results、TensorBoard/CSV logs 與 sample predictions 持久化到 Drive；
- 匯出 `best_model.safetensors`、`calibration.json` 與 ONNX；
- quick mode 不存取 official validation，full final workflow 才執行 locked evaluation。

`scripts/download_artifacts.md` 提供從 Google Drive 帶回 Windows／WSL 的具體指令與 checksum 驗證。

## 11. Local tools 與 Demo

主要 scripts：

```text
scripts/download_data.py
scripts/evaluate.py
scripts/predict.py
scripts/export_onnx.py
scripts/benchmark.py
scripts/update_readme_results.py
```

共同要求：`--config`、`--device {auto,cpu,cuda}`、明確 input/output path、非零失敗 exit code、machine-readable JSON summary。

ONNX 使用 batch 1、固定 512×512 spatial input；preprocessor 負責 pad/resize 與 restore 到 original size。Parity gate 對 raw model sigmoid probabilities 採 `rtol=1e-3`、`atol=1e-4`；calibrated temperature/threshold 先轉成代數上等價的 raw-probability decision threshold，因此 mask 判定與部署結果一致但不會被小 temperature 放大 backend rounding。Thresholded masks 保留 exact-equality diagnostic；只有當兩個 backend 的 threshold-crossing pixels 都位於該 frozen decision threshold 的 `atol` band 內，且 mismatch 同時不超過 32 pixels 與全部輸出的 `1e-4` fraction，才視為 operationally equivalent。任何 band 外或超過 count/fraction 上限的 mask disagreement 仍使 gate 失敗。Logit allclose 與最大 logit/probability error 必須同時記錄，但 logit rounding 本身不取代部署輸出的 probability/mask gate。

Gradio demo 回傳：

- 原始影像；
- segmentation mask overlay；
- 還原到原圖尺寸後的 wound pixel ratio；
- 模型分割 confidence；
- inference time；
- low-confidence「需人工複核」警示。

Demo 不顯示 diagnosis、severity、prognosis 或 treatment recommendation，並固定顯示醫療免責與 FUSeg attribution。Hugging Face Space 預設使用 baseline ONNX／CPU；無本機權重時，只在明確設定 `HF_MODEL_ID` 與 pinned revision 後下載。

## 12. Artifacts 與結果更新

每個 run directory 至少保存：

```text
config.resolved.yaml
provenance.json
best_model.safetensors
last_model.safetensors
trainer_state.pt
calibration.json
results.json
results.partial.json
history.csv
tensorboard/
predictions/
exports/model.onnx
```

`provenance.json` 包含 Git SHA、official data revision、manifest hash、config hash、seed、Python/package versions、device、CUDA/cuDNN 與 checkpoint hash。

README 結果表由 `scripts/update_readme_results.py` 在 marker block 內更新；script 只接受 schema-valid、帶 provenance 且標記為 completed full run 的 `results.json`。其他情況維持「待填」。

## 13. Milestones 與 gates

### M0 — Governance 與 reproducible scaffold

- 建立 `.gitignore`、本機 Git、Apache-2.0 LICENSE、`pyproject.toml`、config loader、目錄骨架、AGENTS、project skill 與文件 placeholders。
- 先確認 `.env`、data、manifests、weights、ONNX 與 generated reports 被 ignore，再 `git init -b main`；不建立 remote。
- Gate：secret-ignore、config/CLI import、Ruff 與基礎 pytest 全數通過。

### M1 — 官方資料取得與 integrity

- 完成 pinned sparse-checkout、manifest、資料驗證、duplicate report 與 internal split。
- Gate：synthetic corruption/pairing/duplicate tests 加官方資料 integration validation；確認 810/200/200 與無 test masks。

### M2 — 最小 executable vertical slice

- 用極小 subset 串通 data loader → augmentation → U-Net → loss → one-epoch training → checkpoint → evaluation → prediction → ONNX → app inference function。
- Gate：loss finite-gradient、known-confusion metrics、model forward shape、checkpoint resume、ONNX parity 與 synthetic fixture inference。
- Smoke metrics 不得進入正式結果表。

### M3 — 完整 training stack 與 Colab

- 加入 SegFormer-B0、兩種 losses、AMP、early stopping、resume、provenance、augmentation visualization 與完整 Colab quick/full workflow。
- Gate：兩模型 CPU mini-train、resume round-trip、notebook 結構測試與 Colab quick-mode 實跑紀錄。

### M4 — Evaluation、calibration 與 error analysis

- 完成 locked validation evaluation、threshold sweep、temperature scaling、TTA uncertainty、bootstrap CI、distribution reports 與 gallery。
- Gate：metrics edge cases、bootstrap reproducibility、calibration serialization、low-confidence rules 與 gallery category tests。

### M5 — Local inference 與 Gradio deployment

- 完成 evaluate、predict、export、benchmark 與 Gradio；支援 CPU/CUDA/ONNX。
- Gate：PyTorch/ONNX parity、CPU/CUDA smoke、benchmark schema 與 app function tests。

### M6 — Release engineering 與完整驗收

- 完成 Dockerfile、GitHub Actions、README、MODEL_CARD、DATA_CARD、CITATION.cff、`.env.example`、90 秒 demo script、Mermaid architecture、Colab badge 與 HF Space placeholder。
- Gate：完整 lint/unit/integration suite、CPU Docker app smoke、clean-clone reproduction audit，以及 raw data／secrets／weights 未被 Git 追蹤的檢查。

每個 milestone 只有在 gate 通過且 `PROGRESS.md` 留有測試證據後才能標示完成。Milestone boundary 先建立本機 commit；只能在使用者明確授權後 push。

## 14. Test strategy

Unit／integration coverage 至少包含：

- data pairing、corrupt file、size mismatch、invalid mask、exact／near duplicate；
- BCE+Dice 與 Focal/Tversky 的 perfect/wrong/empty-mask/finite-gradient cases；
- image/global metrics、known confusion matrix、zero denominators；
- U-Net 與 SegFormer forward shape、upsampling 與 binary logits；
- checkpoint save/resume 與 incompatible metadata rejection；
- threshold sweep、temperature scaling、bootstrap reproducibility；
- confidence cutoff、empty prediction 與 missing-calibration warning；
- ONNX numerical parity 與 mask parity；
- synthetic fixture inference 與 Gradio function outputs；
- result schema 與 README update guardrails。

GitHub Actions 只使用 synthetic fixtures，不下載 medical data 或 pretrained weights，執行：

```text
ruff check .
ruff format --check .
pytest -q
```

Data integration、Colab GPU quick mode、CUDA benchmark 與 Docker app smoke 另列為明確的 manual／integration gates，不假裝已由一般 unit CI 覆蓋。

## 15. Release 文件

- `README.md`：問題定義、verified data scale、方法、重現指令、結果表、error-analysis policy、Mermaid architecture、Colab/HF placeholders、限制、醫療免責與 90 秒 demo script。
- `DATA_CARD.md`：來源、revision、資料規模、annotation、split limitation、license ambiguity、禁止再散布與資料驗證摘要。
- `MODEL_CARD.md`：intended use、out-of-scope use、training protocol、metrics、confidence、limitations、ethical/medical caveats 與 weight-release status。
- `CITATION.cff`：software author 使用已確認的 GitHub identity `kuotunyu`；未提供的 ORCID 不填寫，並引用 FUSeg 論文。
- `LICENSE`：Apache License 2.0，明確排除第三方 data 與 model artifacts。

## 16. Decision Log

| 日期 | 決策 | 狀態 |
|---|---|---|
| 2026-07-19 | 使用 `PROJECT_PLAN.md` + `PROGRESS.md` 分離穩定規格與即時進度 | Locked |
| 2026-07-19 | Official validation 鎖定為最終評估，official train 建 internal dev | Locked |
| 2026-07-19 | Full mode 採單-seed ablation + selected configs 三 seeds | Locked |
| 2026-07-19 | Confidence 採 temperature calibration + 2-view horizontal-flip TTA | Locked |
| 2026-07-19 | WoundScope code 採 Apache-2.0 | Locked |
| 2026-07-19 | 正式實作時初始化 local Git，但不設定 remote | Locked |
| 2026-07-19 | 人讀文件與 UI 以正體中文為主，專有名詞保留原文 | Locked |
| 2026-07-19 | Pre-implementation 先完成兩份文件並停在 review gate | Locked |
| 2026-08-03 | Pinned revision 的 7 組 train–validation exact duplicates 固定採 `exclude_train`：只排除 train copies、保留 official validation 200 張；validation 不參與任何 selection/calibration，pHash 只作警告 | Locked |
| 2026-07-19 | HF Space Docker 明確安裝 PyTorch CPU wheel，僅包含 app/export dependencies | Locked |
| 2026-08-03 | ONNX parity 對 raw model sigmoid probability 維持 `rtol=1e-3`／`atol=1e-4`；temperature-calibrated decision 轉為等價 raw threshold，mask disagreement 僅可發生在兩端都位於 `atol` decision band且同時不超過 32 pixels／`1e-4` fraction，exact mask equality 與 logit error 保留為 diagnostics | Locked |
| 2026-08-04 | 授權公開 `kuotunyu/WoundScope`；README、GitHub Description 與 About 以正體中文（`zh-TW`）為主，專有名詞保留原文；GitHub Contributors 只允許 `kuotunyu`，不使用 co-author 或 bot commit；結果 provenance 的舊 SHA 另以 tag 保留 | Locked |
| 2026-08-04 | Hugging Face Space 僅可先建立 deterministic code-only candidate；在 FUSeg 權利人以可保存的書面回覆明確確認 derived model weights、ONNX、attribution、可見性與 public non-commercial inference 前，固定為 `PERMISSION_PENDING`，不得建立 model-backed live Space、model repository 或上傳任何 model artifact | Locked |

## 17. Review gate

開始正式實作前，確認：

- [x] `PROJECT_PLAN.md` 的科學 protocol、授權政策與 milestones 可接受。
- [x] `PROGRESS.md` 的續作格式足以在中斷後恢復工作。
- [x] 同意正式實作後先做 M0，再依序執行 M1–M6。
- [x] 同意不在本機自動執行 full training，也不對外推送。

Review gate 已於 2026-07-19 由使用者明確解除；cross-split exact-duplicate mitigation 已於 2026-08-03 鎖定為 `exclude_train`。

Review gate、M0–M6、Public GitHub release 與 hosted CI 已完成；後續只在新增 material scientific decision 時重開 milestone，日常 bug fix、security update 與 release maintenance 依既有 gates 驗證。
