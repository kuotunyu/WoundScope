# WoundScope Model Card

## Model status

Colab full training、三-seed locked official-validation evaluation、ONNX parity／benchmark 與 safe handoff 均已完成並通過 schema、inventory、size、SHA-256 與 privacy 驗證。正式 checkpoints／ONNX 仍只保存在 private Drive，未包含於 repository；下列數字只代表 pinned FUSeg official validation，不是 official test、外部或臨床效能。

## Intended use

WoundScope 是研究與工程展示用的 binary foot-ulcer segmentation pipeline。輸入 RGB 影像，輸出單通道 logits、binary mask、原始尺寸 wound-pixel ratio 與模型分割信心。

適用：reproducibility study、模型比較、MLOps／ONNX demo。非適用：疾病診斷、嚴重度分級、預後、治療建議、緊急程度判斷或無人工複核的臨床決策。

## Candidate architectures

- Baseline：EfficientNet-B0 encoder U-Net，ImageNet initialization。
- Advanced：SegFormer-B0 pretrained initialization。
- Output：single-channel logits；inference threshold 與 temperature 由 internal dev 凍結。

## Training protocol

Pinned split 的 7 張 exact train copies 在所有 training 前以鎖定的 `exclude_train` 政策排除，official validation 200 張完整保留且不參與調參。比較 BCE+Dice 與 Focal+Tversky；seed 42 做 architecture × loss selection，每架構選定 loss 後執行 seeds 42/43/44。Full mode 上限 50 epochs、patience 8、batch 8、gradient accumulation 2、CUDA AMP。每 epoch 保存可 resume state 與 provenance。

## Evaluation

Official validation 報告 image-level/global Dice、IoU、precision、recall、specificity，含 mean、median、SD、IQR、三 seeds mean±SD 及 image-cluster bootstrap 2,000 次 95% CI。Error gallery 固定涵蓋最佳、最差、小面積、低光與背景干擾，且不得只選漂亮案例。

| Model | Loss | Seeds | Dice mean±SD (95% CI) | IoU | Precision | Recall | Specificity |
|---|---|---|---:|---:|---:|---:|---:|
| EfficientNet-B0 U-Net | BCE+Dice | 42/43/44 | 0.8508±0.0035 (0.8218–0.8768) | 0.7772±0.0039 | 0.8581±0.0056 | 0.9039±0.0032 | 0.9989±0.0000 |
| SegFormer-B0 | BCE+Dice | 42/43/44 | 0.8270±0.0040 (0.7973–0.8550) | 0.7437±0.0053 | 0.8326±0.0038 | 0.8832±0.0045 | 0.9988±0.0000 |

各 metric 為三個 training seeds 的 image-level mean 之 mean±sample SD；Dice CI 統合三個 training seeds 的對齊 image-level values，並使用 bootstrap RNG seed=42 做 2,000 次 image-cluster percentile bootstrap。U-Net 在此 locked split 的 observed Dice 較高，但沒有 paired significance test，不能解讀為跨資料來源或臨床上的普遍優勢。

## Confidence and human review

Confidence 結合 calibrated probability entropy 與 original/horizontal-flip TTA agreement。低於 internal-dev 第 10 百分位、prediction 為空或 calibration metadata 缺失時顯示「需人工複核」。此數值不是診斷或臨床信心；即使分數高也不能免除人工審查。

## Limitations

FUSeg 沒有 patient ID，pinned official split 含 7 組 train–validation exact duplicates，且沒有 public test masks。模型尚未做外部、多中心、膚色 subgroup、裝置或照明 robustness validation。詳見 [DATA_CARD.md](DATA_CARD.md)。

## Artifact provenance

每個正式 run 包含 config hash、official source revision、manifest hash、Git SHA、seed、environment/device versions、checkpoint hash、`best_model.safetensors`、`last_model.safetensors`、trainer state、calibration、results、logs、predictions 與 ONNX parity report。Training source 為 `c7ec6060f1bd0a813a890b95b50c2855d3c2640c`；safe-handoff repair implementation 為 `8345176593e3fe5a3c95e2f053306229e5a09455`。下載的 privacy-safe result ZIP SHA-256 為 `6ff4d1f14f4242c72fa2ef3382bcbfadc15df93dd4aeb739ae1864f7de24f221`，含 52 個 aggregate/config/provenance/chart artifacts，不含 weights、ONNX binaries、來源影像或 private gallery。授權確認前不公開權重。
