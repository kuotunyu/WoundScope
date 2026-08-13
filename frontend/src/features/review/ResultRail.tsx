import { Activity, Clock3, Cpu, ScanSearch } from "lucide-react";

import type { PredictionResponse } from "../../lib/api/types";

interface ResultRailProps {
  result: PredictionResponse;
}

const REASON_LABELS: Record<string, string> = {
  confidence_below_dev_cutoff: "模型分割信心低於 development cutoff",
  high_entropy: "像素機率不確定性偏高",
  low_tta_agreement: "Test-time augmentation 一致性偏低",
};

const PERCENT_FORMAT = new Intl.NumberFormat("zh-TW", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const MILLISECOND_FORMAT = new Intl.NumberFormat("zh-TW", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function ResultRail({ result }: ResultRailProps) {
  return (
    <aside className="result-rail" aria-labelledby="result-title" aria-live="polite">
      <div className={`review-verdict ${result.low_confidence ? "needs-review" : "review-ready"}`}>
        <ScanSearch aria-hidden="true" />
        <div>
          <span className="eyebrow">複核狀態</span>
          <h2 id="result-title">
            {result.low_confidence ? "需要人工複核" : "模型輸出可供複核"}
          </h2>
          <p>
            {result.low_confidence
              ? "請優先檢查邊界與漏分區域；狀態同時以文字標示。"
              : "仍須由研究人員檢視，不代表臨床判斷。"}
          </p>
        </div>
      </div>

      <div className="result-metrics">
        <article>
          <Activity aria-hidden="true" />
          <span>Mask 面積比例</span>
          <strong>{PERCENT_FORMAT.format(result.wound_pixel_ratio)}</strong>
          <small>預測 mask pixels／影像 pixels</small>
        </article>
        <article>
          <ScanSearch aria-hidden="true" />
          <span>{result.confidence_label}</span>
          <strong>{PERCENT_FORMAT.format(result.confidence_score)}</strong>
          <small>僅供 segmentation review 排序</small>
        </article>
        <article>
          <Clock3 aria-hidden="true" />
          <span>推論時間</span>
          <strong>{MILLISECOND_FORMAT.format(result.inference_ms)} ms</strong>
          <small>單次本機推論時間</small>
        </article>
        <article>
          <Cpu aria-hidden="true" />
          <span>執行 provider</span>
          <strong>{result.provider}</strong>
          <small>由本機 runtime 回報</small>
        </article>
      </div>

      {result.review_reasons.length > 0 && (
        <div className="review-reasons">
          <strong>複核原因</strong>
          <ul>
            {result.review_reasons.map((reason) => (
              <li key={reason}>{REASON_LABELS[reason] ?? "模型輸出需要額外人工檢查"}</li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
