# WoundScope v0.2.2 收尾設計

> 狀態：已完成並通過 local release verification

## 目標

將已合併的 React／FastAPI 複核工作台整理為 `v0.2.2` software release，並把「尚未取得 FUSeg 衍生權重公開授權」從公開頁面的待辦／故障語言，收斂為刻意且穩定的 code-only 發布邊界。

## 公開定位

- WoundScope 是可重現、可複核的 Medical Computer Vision GitHub portfolio project。
- 公開 repository 提供 code、aggregate evidence、synthetic fixtures、React UI 與 FastAPI integration。
- 公開 model artifacts 與 hosted live inference 不在目前專案發布範圍；不再呈現為等待使用者處理的 active blocker。
- 有合法取得且自行保管 artifacts 的使用者，仍可依 README 在本機啟用 private review workflow。
- 不宣稱 FUSeg 權利人已核准或拒絕；既有授權不確定性與禁止公開 weights／ONNX 的歷史事實保留。

## 介面與文件

- Provenance rail 顯示 `v0.2.2 · code-only`。
- 原「權限狀態／衍生權重待書面確認」改為「公開範圍／模型 artifacts 不隨專案發布」。
- README 將 Hugging Face Space 的等待狀態改為穩定 scope 說明，保留 archived deployment policy 的連結。
- Hugging Face deployment 文件標記為 archived／future-only；若未來另案重啟，仍必須先取得可保存的書面確認。
- 已完成的 UI design documents 改為「已完成」，不再留下「待實作」或「待使用者複核」。

## Release 邊界

- 版本同步為 `0.2.2`：Python package、frontend package、lock、CITATION、API metadata、README 與 UI。
- 新增 zh-TW-first release notes，說明 Scientific Console、使用導引、accessibility／responsive 與 code-only scope。
- 不移動既有 tags，不改寫 `v0.1.0` 結果 provenance，不重跑 training。
- GitHub Release 不附加 data、weights、ONNX、medical images、masks、private gallery 或 image-level artifacts。

## 驗證

- TDD 驗證 release metadata 與 provenance rail 的使用者可見行為。
- Python 3.11／3.12-compatible full pytest、Ruff、format、privacy audit、package build。
- Frontend Vitest、TypeScript、ESLint、production build。
- Git／identity／diff checks；PR hosted CI 全綠後才 merge、tag 與發布 Release。
