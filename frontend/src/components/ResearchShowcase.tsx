import { ArrowRight, Binary, CircleDashed, Layers3 } from "lucide-react";

import type { ModelStatus } from "../lib/api/types";
import { WorkflowGuide } from "./WorkflowGuide";

interface ResearchShowcaseProps {
  status: ModelStatus | null;
  statusError: boolean;
}

export function ResearchShowcase({ status, statusError }: ResearchShowcaseProps) {
  return (
    <section className="showcase" aria-labelledby="showcase-title">
      <div className="showcase-copy">
        <h1 id="showcase-title">WoundScope 傷口分割複核工作台</h1>
        <p className="lede">
          以 data integrity、segmentation、calibration、ONNX parity 與 artifact
          provenance 建立可重現、可複核的研究工作流。
        </p>
        <p className="research-context">
          <span>Medical Computer Vision</span>
          <span>Research prototype</span>
        </p>

        <div className="mode-status" role="status" aria-live="polite">
          <div className="mode-icon" aria-hidden="true">
            <CircleDashed size={23} />
          </div>
          <div>
            <span className="status-label">{statusError ? "服務狀態" : "目前工作區"}</span>
            <h2>{statusError ? "無法取得本機模型狀態" : "研究展示模式"}</h2>
            <p>
              {statusError
                ? "介面仍可瀏覽；請確認本機 FastAPI 服務後重新整理。"
                : status?.message ?? "正在確認 code-only 與 local model 狀態…"}
            </p>
          </div>
        </div>

        <WorkflowGuide variant="showcase" />

        <div className="showcase-links">
          <a
            className="text-link"
            href="https://github.com/kuotunyu/WoundScope/blob/main/DATA_CARD.md"
          >
            查看資料治理
            <ArrowRight size={17} aria-hidden="true" />
          </a>
          <a className="text-link" href="#provenance">
            檢視 provenance
            <ArrowRight size={17} aria-hidden="true" />
          </a>
        </div>
      </div>

      <div className="research-plate" aria-label="研究流程介面示意，非醫療影像或模型預測">
        <div className="plate-meta">
          <strong>Segmentation 複核平面</strong>
          <span>512 × 512</span>
        </div>
        <svg
          className="contour-map"
          viewBox="70 82 500 350"
          role="img"
          aria-label="抽象的分割輪廓與網格，不代表病患影像"
        >
          <defs>
            <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
              <path d="M 32 0 L 0 0 0 32" fill="none" className="grid-line" />
            </pattern>
            <linearGradient id="contourFill" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" className="contour-start" />
              <stop offset="1" className="contour-end" />
            </linearGradient>
          </defs>
          <rect width="640" height="470" fill="url(#grid)" />
          <path
            className="outer-contour"
            d="M128 287C109 227 142 151 207 123C270 96 350 101 411 134C468 164 515 224 501 281C487 337 425 380 359 387C293 394 226 374 180 347C153 331 139 313 128 287Z"
          />
          <path
            className="inner-contour"
            d="M212 286C195 252 209 207 246 187C282 168 333 174 364 198C395 222 411 265 395 298C378 333 335 350 295 343C256 337 226 316 212 286Z"
          />
          <path className="scan-line" d="M74 236H566" />
          <circle className="target-point" cx="303" cy="263" r="6" />
          <path className="axis-mark" d="M303 244V282M284 263H322" />
        </svg>

        <div className="plate-footer">
          <div className="plate-legend">
            <span>
              <Layers3 size={18} aria-hidden="true" />
              Overlay 邊界
            </span>
            <span>
              <Binary size={18} aria-hidden="true" />
              Binary semantic segmentation
            </span>
          </div>
          <p className="plate-note">介面示意圖｜不含醫療影像、mask 或虛構 prediction</p>
        </div>
      </div>
    </section>
  );
}
