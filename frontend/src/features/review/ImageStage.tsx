import { type CSSProperties, useEffect, useRef, useState } from "react";
import { Expand, Minimize2 } from "lucide-react";

import type { PredictionResponse } from "../../lib/api/types";

type ViewMode = "compare" | "original" | "overlay" | "mask";

interface ImageStageProps {
  previewUrl: string;
  result: PredictionResponse;
}

const VIEW_LABELS: Array<{ mode: ViewMode; label: string }> = [
  { mode: "compare", label: "比較" },
  { mode: "original", label: "原圖" },
  { mode: "overlay", label: "Overlay" },
  { mode: "mask", label: "Mask" },
];

export function ImageStage({ previewUrl, result }: ImageStageProps) {
  const [view, setView] = useState<ViewMode>("compare");
  const [comparison, setComparison] = useState(50);
  const [opacity, setOpacity] = useState(45);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function syncFullscreen() {
      setIsFullscreen(document.fullscreenElement === stageRef.current);
    }
    document.addEventListener("fullscreenchange", syncFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncFullscreen);
  }, []);

  async function toggleFullscreen() {
    if (document.fullscreenElement === stageRef.current) {
      await document.exitFullscreen?.();
    } else {
      await stageRef.current?.requestFullscreen?.();
    }
  }

  const stageStyle = {
    "--comparison-position": `${comparison}%`,
    "--overlay-opacity": opacity / 100,
  } as CSSProperties;

  return (
    <section
      className="image-stage"
      ref={stageRef}
      data-testid="image-stage"
      aria-label="影像複核畫布"
    >
      <header className="stage-toolbar">
        <div className="view-switcher" role="group" aria-label="影像圖層">
          {VIEW_LABELS.map(({ mode, label }) => (
            <button
              key={mode}
              type="button"
              aria-pressed={view === mode}
              onClick={() => setView(mode)}
            >
              {label}
            </button>
          ))}
        </div>
        <button className="fullscreen-button" type="button" onClick={toggleFullscreen}>
          {isFullscreen ? <Minimize2 aria-hidden="true" /> : <Expand aria-hidden="true" />}
          {isFullscreen ? "退出全螢幕" : "進入全螢幕"}
        </button>
      </header>

      <div className={`image-canvas view-${view}`} style={stageStyle}>
        <img
          className="original-layer"
          src={previewUrl}
          alt="本機待複核原始影像"
          width="1200"
          height="900"
          draggable="false"
        />
        {(view === "compare" || view === "overlay") && (
          <img
            className="overlay-layer"
            src={result.overlay_data_url}
            alt="模型預測 Overlay"
            width="1200"
            height="900"
            draggable="false"
          />
        )}
        {view === "mask" && (
          <img
            className="mask-layer"
            data-testid="mask-layer"
            src={result.mask_data_url}
            alt="模型預測 binary mask"
            width="1200"
            height="900"
            draggable="false"
          />
        )}
        {view === "compare" && (
          <span className="comparison-divider" aria-hidden="true">
            <span />
          </span>
        )}
      </div>

      <div className="stage-controls">
        <label className={view === "compare" ? "" : "is-muted"}>
          <span>
            Overlay 比較位置 <output>{comparison}%</output>
          </span>
          <input
            type="range"
            min="0"
            max="100"
            value={comparison}
            disabled={view !== "compare"}
            aria-label="Overlay 比較位置"
            onChange={(event) => setComparison(Number(event.target.value))}
          />
        </label>
        <label className={view === "original" || view === "mask" ? "is-muted" : ""}>
          <span>
            Overlay 透明度 <output>{opacity}%</output>
          </span>
          <input
            type="range"
            min="20"
            max="80"
            value={opacity}
            disabled={view === "original" || view === "mask"}
            aria-label="Overlay 透明度"
            onChange={(event) => setOpacity(Number(event.target.value))}
          />
        </label>
      </div>
      <p className="stage-legend">
        <span aria-hidden="true" /> 珊瑚色填滿與虛線邊界代表模型預測區域；所有判讀仍以文字狀態為準。
      </p>
    </section>
  );
}
