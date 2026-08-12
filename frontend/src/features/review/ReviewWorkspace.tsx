import { FileImage, LoaderCircle, LockKeyhole, RotateCcw, ScanLine } from "lucide-react";

import type { ModelStatus } from "../../lib/api/types";
import { ImageStage } from "./ImageStage";
import { ResultRail } from "./ResultRail";
import { useReviewSession } from "./useReviewSession";

interface ReviewWorkspaceProps {
  status: ModelStatus;
}

export function ReviewWorkspace({ status }: ReviewWorkspaceProps) {
  const session = useReviewSession();
  const canSubmit = Boolean(session.file) && session.phase !== "loading";

  return (
    <section
      className="review-workspace"
      aria-labelledby="review-workspace-title"
      aria-live="polite"
    >
      <header className="workspace-intro">
        <div>
          <p className="kicker">Local Review · Private Runtime</p>
          <h1 id="review-workspace-title">傷口分割複核工作台</h1>
          <p>
            並排檢視原圖、Overlay 與 binary mask；每次推論均由你明確啟動，結果不作臨床診斷。
          </p>
        </div>
        <div className="local-runtime-note">
          <LockKeyhole aria-hidden="true" />
          <div>
            <strong>本機處理</strong>
            <span>{status.model_label} · {status.provider}</span>
          </div>
        </div>
      </header>

      <div className="upload-console">
        <label className={`upload-field ${session.file ? "has-file" : ""}`}>
          <input
            type="file"
            name="review-image"
            accept="image/png,image/jpeg,image/webp"
            autoComplete="off"
            aria-label="選擇傷口影像"
            aria-describedby="upload-help upload-error"
            onChange={(event) => session.selectFile(event.target.files?.[0] ?? null)}
          />
          <FileImage aria-hidden="true" />
          <span>
            <strong>{session.file ? "影像已載入本機預覽" : "選擇一張影像開始"}</strong>
            <small id="upload-help">PNG、JPEG、WebP · 最大 12 MiB · 不自動上傳</small>
          </span>
        </label>

        <div className="upload-actions">
          {session.phase === "error" ? (
            <button className="primary-action" type="button" onClick={session.submitPrediction}>
              <RotateCcw aria-hidden="true" />
              重新嘗試
            </button>
          ) : (
            <button
              className="primary-action"
              type="button"
              disabled={!canSubmit}
              onClick={session.submitPrediction}
            >
              {session.phase === "loading" ? (
                <LoaderCircle className="spinner" aria-hidden="true" />
              ) : (
                <ScanLine aria-hidden="true" />
              )}
              {session.phase === "loading" ? "正在執行分割…" : "開始分割複核"}
            </button>
          )}
        </div>
        <p
          className="field-message"
          id="upload-error"
          role={session.fieldError || session.requestError ? "alert" : undefined}
          aria-live="polite"
        >
          {session.fieldError ?? session.requestError ?? "影像僅保留於目前本機工作階段。"}
        </p>
      </div>

      {session.previewUrl && session.result ? (
        <div className="review-grid">
          <ImageStage previewUrl={session.previewUrl} result={session.result} />
          <ResultRail result={session.result} />
        </div>
      ) : session.previewUrl ? (
        <div className={`preview-state ${session.phase === "loading" ? "is-loading" : ""}`}>
          <img
            src={session.previewUrl}
            alt="待複核原始影像預覽"
            width="1200"
            height="900"
          />
          <div>
            <span className="eyebrow">{session.phase === "loading" ? "Inference" : "Ready"}</span>
            <h2>{session.phase === "loading" ? "正在建立可複核的預測圖層" : "等待你明確啟動推論"}</h2>
            <p>
              {session.phase === "loading"
                ? "請保留此頁開啟；完成後將顯示 Overlay、Mask 與非臨床 confidence。"
                : "選取影像不會自動送出，按下「開始分割複核」後才會傳給本機 API。"}
            </p>
          </div>
        </div>
      ) : (
        <div className="empty-review-state">
          <span aria-hidden="true">01</span>
          <div>
            <h2>先建立一個暫時性的本機 review session</h2>
            <p>不保存檔名、不建立 gallery，也不把影像寫入 repository。</p>
          </div>
        </div>
      )}
    </section>
  );
}
