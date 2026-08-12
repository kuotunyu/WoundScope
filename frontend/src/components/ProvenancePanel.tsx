import { Fingerprint, GitCommitHorizontal, Scale, ShieldAlert } from "lucide-react";

import type { ModelStatus } from "../lib/api/types";

interface ProvenancePanelProps {
  status: ModelStatus | null;
}

export function ProvenancePanel({ status }: ProvenancePanelProps) {
  return (
    <section className="provenance" id="provenance" aria-labelledby="provenance-title">
      <div>
        <span className="eyebrow">證據，不是裝飾</span>
        <h2 id="provenance-title">每個結果，都必須知道從哪裡來。</h2>
      </div>
      <dl className="provenance-grid">
        <div>
          <GitCommitHorizontal aria-hidden="true" />
          <dt>Release</dt>
          <dd>v0.2.1 · code-only</dd>
        </div>
        <div>
          <Fingerprint aria-hidden="true" />
          <dt>Model artifact</dt>
          <dd>{status?.model_sha256_prefix ?? "未公開／不可用"}</dd>
        </div>
        <div>
          <Scale aria-hidden="true" />
          <dt>Calibration</dt>
          <dd>{status?.calibration_available ? "Dev-only metadata 已就緒" : "未公開"}</dd>
        </div>
        <div>
          <ShieldAlert aria-hidden="true" />
          <dt>權限狀態</dt>
          <dd>衍生權重待書面確認</dd>
        </div>
      </dl>
      <details>
        <summary>查看研究與 artifact 邊界</summary>
        <div className="provenance-detail">
          <p>
            公開 repository 僅提供 code、aggregate evidence 與 synthetic fixtures。FUSeg
            images／masks、checkpoints、ONNX 與 image-level artifacts 均不公開。
          </p>
          <p>
            Official Validation 不參與 loss selection、threshold sweep 或 temperature scaling；
            confidence 是模型分割信心，不是臨床信心。
          </p>
        </div>
      </details>
    </section>
  );
}
