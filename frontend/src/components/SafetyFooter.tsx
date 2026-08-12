import { Shield } from "lucide-react";

export function SafetyFooter() {
  return (
    <footer className="safety-footer">
      <Shield size={22} aria-hidden="true" />
      <p>
        <strong>研究用途，非臨床診斷。</strong>
        不輸出疾病診斷、嚴重度、預後或治療建議；任何分割結果都需由合格專業人員人工複核。請勿上傳可識別個人的健康資訊（PHI）。
      </p>
      <p className="attribution">Data source: FUSeg · UWM Big Data Lab</p>
    </footer>
  );
}
