import { Fingerprint, GitCommitHorizontal, Scale, ShieldAlert } from "lucide-react";

import type { ModelStatus } from "../lib/api/types";

interface ProvenancePanelProps {
  status: ModelStatus | null;
}

export function ProvenancePanel({ status }: ProvenancePanelProps) {
  return (
    <section className="provenance" id="provenance" aria-labelledby="provenance-title">
      <div>
        <span className="eyebrow">Evidence, not decoration</span>
        <h2 id="provenance-title">每個結果，都必須知道從哪裡來。</h2>
      </div>
      <div className="provenance-grid">
        <article>
          <GitCommitHorizontal aria-hidden="true" />
          <span>Release</span>
          <strong>v0.2.1 · code-only</strong>
        </article>
        <article>
          <Fingerprint aria-hidden="true" />
          <span>Model artifact</span>
          <strong>{status?.model_sha256_prefix ?? "Private / unavailable"}</strong>
        </article>
        <article>
          <Scale aria-hidden="true" />
          <span>Calibration</span>
          <strong>{status?.calibration_available ? "Dev-only metadata ready" : "Not exposed"}</strong>
        </article>
        <article>
          <ShieldAlert aria-hidden="true" />
          <span>Permission</span>
          <strong>Derived weights pending</strong>
        </article>
      </div>
      <details>
        <summary>展開研究與 artifact 邊界</summary>
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
