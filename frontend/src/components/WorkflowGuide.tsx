import { ArrowRight } from "lucide-react";

interface WorkflowGuideProps {
  variant: "showcase" | "review";
}

const guideContent = {
  showcase: {
    title: "使用流程",
    meta: "Local review path",
    steps: [
      ["準備 artifacts", "在自己的機器準備 private ONNX 與 calibration metadata。"],
      ["啟動本機工作台", "設定環境變數並啟動本機 FastAPI。"],
      ["上傳並複核", "執行 segmentation、比較圖層，再由專業人員人工確認。"],
    ],
  },
  review: {
    title: "操作流程",
    meta: "3 steps",
    steps: [
      ["選擇影像", "PNG、JPEG 或 WebP；選取後只建立本機預覽。"],
      ["明確開始分割", "按下主要按鈕後，影像才會傳給本機 API。"],
      ["比較並人工複核", "檢視 Original、Overlay、Mask、confidence 與 review reasons。"],
    ],
  },
} as const;

export function WorkflowGuide({ variant }: WorkflowGuideProps) {
  const content = guideContent[variant];
  const titleId = `workflow-guide-${variant}`;

  return (
    <section className={`workflow-guide workflow-guide-${variant}`} aria-labelledby={titleId}>
      <div className="workflow-guide-heading">
        <h2 id={titleId}>{content.title}</h2>
        <span>{content.meta}</span>
      </div>
      <ol className="workflow-steps">
        {content.steps.map(([title, description], index) => (
          <li key={title}>
            <span className="workflow-index" aria-hidden="true">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div>
              <strong>{title}</strong>
              <p>{description}</p>
            </div>
          </li>
        ))}
      </ol>
      {variant === "showcase" ? (
        <a
          className="setup-link"
          href="https://github.com/kuotunyu/WoundScope#啟動分割複核工作台"
        >
          查看本機啟用方式
          <ArrowRight size={18} aria-hidden="true" />
        </a>
      ) : null}
    </section>
  );
}
