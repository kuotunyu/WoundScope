# Security Policy

## 支援版本

安全修正以最新的 `main` 與最新 GitHub Release 為主。舊版只在問題仍可於目前版本重現時處理。

## 私下回報安全問題

請勿以公開 Issue 回報尚未修正的 vulnerability。請使用 GitHub repository 的
[private vulnerability reporting](https://github.com/kuotunyu/WoundScope/security/advisories/new)
建立 private Security Advisory，並提供：

- 受影響的 version／commit；
- 可使用 synthetic input 重現的最小步驟；
- 可能影響與建議 mitigation；
- 已移除 secret、token、`.env` values、私人路徑與 medical data 的 logs。

請勿上傳 FUSeg images／masks、其他醫療影像、image-level manifests／results、private
galleries、checkpoints、模型權重、ONNX binaries 或任何可識別個人的資料。

## 回應原則

維護者會先確認可重現性與影響範圍，再於 private advisory 中協調修正與 disclosure。
Dependency update 由 `kuotunyu` 人工審查並以 owner-authored commit 套用，避免 bot-authored
commits 改變 repository contributor policy。

## 醫療界線

WoundScope 是研究與工程展示，不是醫療器材。Security report 不應包含真實個案，模型輸出
也不得用於診斷、分級、預後或治療決策。
