# WoundScope Model Card

## Model status

目前沒有 verified full-training checkpoint；所有 performance 欄位為「待填」。Repository 中的 synthetic／quick smoke 僅驗證程式可執行，不代表醫療影像效能。

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

| Model | Loss | Seeds | Dice | IoU | Precision | Recall | Specificity |
|---|---|---|---|---|---|---|---|
| EfficientNet-B0 U-Net | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| SegFormer-B0 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

## Confidence and human review

Confidence 結合 calibrated probability entropy 與 original/horizontal-flip TTA agreement。低於 internal-dev 第 10 百分位、prediction 為空或 calibration metadata 缺失時顯示「需人工複核」。此數值不是診斷或臨床信心；即使分數高也不能免除人工審查。

## Limitations

FUSeg 沒有 patient ID，pinned official split 含 7 組 train–validation exact duplicates，且沒有 public test masks。模型尚未做外部、多中心、膚色 subgroup、裝置或照明 robustness validation。詳見 [DATA_CARD.md](DATA_CARD.md)。

## Artifact provenance

每個正式 run 必須包含 config hash、official source revision、manifest hash、Git SHA、seed、environment/device versions、checkpoint hash、`best_model.safetensors`、`last_model.safetensors`、trainer state、calibration、results、logs、predictions 與 ONNX parity report。授權確認前不公開權重。
