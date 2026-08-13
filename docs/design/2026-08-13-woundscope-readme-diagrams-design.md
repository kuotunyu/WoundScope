# WoundScope README 圖解設計

> 狀態：使用者已核准原始設計與可讀性修訂；本次 revision 以單一使用者視角、zh-TW-first copy 與 22px 基準字級為準

## 1. 目的與主要讀者

README 的第一優先讀者是一般 GitHub 訪客，但圖解不再把 GitHub 訪客、FUSeg 與研究者／ML Engineer 排成三種同層角色。所有人都從單一「使用者」視角閱讀同一套系統；FUSeg 是研究管線內的固定資料來源，不是 persona。讀者應能在約 60 秒內回答三個問題：

1. WoundScope 是什麼，公開 repository 與 private artifacts 的邊界在哪裡？
2. 研究結果如何從資料治理走到可複核的 aggregate evidence？
3. 本機複核時，Browser、React、FastAPI 與 ONNX Runtime 如何互動？

技術招聘者／ML Engineer 與 Medical CV 研究者仍能看見可重現性、API 邊界、artifact provenance、locked evaluation 與 privacy design，但不需要先判斷自己屬於哪種角色，也不把 README 變成完整設計規格書。

## 2. 設計原則

- 維持正體中文（zh-TW）為主，React、FastAPI、ONNX Runtime、Official Validation 等專有名詞保留原文。
- 每張圖只回答一個核心問題；不重複用不同圖型描述同一件事。
- 使用 GitHub 原生 Mermaid，避免需要額外託管的 raster 圖與實驗性 C4 syntax。
- 節點文字控制在兩行內；主要閱讀方向優先採左至右，過寬時改為分層式 top-down。
- WoundScope 的沉靜醫療研究語言由 UI screenshot 與整體敘事延續；Mermaid semantic colors 交由 GitHub 的 light／dark adaptive theme，避免固定前景色在 dark mode 失去對比。
- 不只依靠顏色傳達 public／private、success／boundary；同時使用明確標籤、線型與節點文字。
- 不加入 diagnosis、severity、clinical efficacy、patient-wise split、official-test performance 或其他未驗證 claim。

## 3. README 資訊順序

README 依以下順序重整：

1. Project title、badges、價值主張與非臨床聲明。
2. UI showcase screenshot 與一句操作定位。
3. 「60 秒看懂 WoundScope」：System Context＋Architecture 圖。
4. 「可重現研究 Pipeline」：Research Workflow 圖。
5. Verified Results：既有 aggregate chart、結果表與科學限制。
6. 「本機複核如何運作」：Local Review Sequence Diagram。
7. Quick Start、工程可信度、安全界線、文件與 Releases。

既有 screenshot 與 aggregate model comparison SVG 保留。現有「系統設計與關鍵特性」三點摘要收斂為 context 圖前的短導讀；現有 pipeline Mermaid 由新 Research Workflow 圖取代，不再保留兩份相似 pipeline。

## 4. Diagram 1 — System Context＋Architecture

### 回答的問題

「使用者如何從公開專案入口理解、重現或啟動 WoundScope，而公開證據與私有模型產物的邊界在哪裡？」

### 圖型

使用分層式 `flowchart TB` 的 C4-lite 視圖，不使用 Mermaid experimental C4 syntax。先收斂入口，再分流到研究管線與本機複核，避免三個外部角色並排迫使整圖縮小。

### 節點與邊界

- Actor：單一 `使用者`。
- Public entry：`GitHub Repository／Public Colab`；FUSeg 固定 revision 收進研究管線節點，不獨立扮演角色。
- WoundScope system boundary：
  - `React Review Workbench`
  - `FastAPI Review API`
  - `Model Runtime／ONNX Runtime`
  - `Reproducible Research Pipeline`
- Private boundary：`Google Drive／local artifacts`，包含 checkpoints、calibration、ONNX 與 image-level outputs，但圖上只列 artifact 類型，不列實際路徑或檔名。
- Public outputs：code、aggregate evidence、Model Card／Data Card、GitHub Release。

### 關係

- 使用者由同一公開入口閱讀 code／aggregate evidence、在 Public Colab 重現 pipeline，或啟動本機 React 工作台。
- Pipeline 使用 FUSeg 固定 revision，並把 private artifacts 寫入個人 Drive 或本機 artifact directory。
- 本機工作台由 React 呼叫 FastAPI；只有使用者自行提供 private ONNX／calibration 時才進入 local-review mode。
- Public repository 與 private artifact boundary 使用不同線型及文字標籤，避免誤解 repository 內含 model weights。

## 5. Diagram 2 — Reproducible Research Workflow

### 回答的問題

「正式結果如何產生，以及哪些 gate 防止資料洩漏、selection leakage 與不可追溯結果？」

### 圖型

使用分成三個 subgraph 的 `flowchart LR`：Data Governance、Experiment、Evidence & Handoff。

### 流程

圖中保留實際 pipeline contract，不虛構 stage：

1. `FUSeg pinned revision`
2. `Data integrity`：pairing、decode、binary mask、SHA-256／pHash audit
3. `exclude_train`：排除 7 張 exact train copies，保留 Official Validation 200 張
4. `Quick GPU gate`
5. `2 models × 2 losses` 的 internal-dev comparison
6. `Locked loss selection`：只使用 internal dev
7. `3-seed final runs`：42／43／44
8. `Official Validation`：selection 與 calibration 凍結後才進入
9. `2,000× image-level Bootstrap`
10. `ONNX parity／CPU benchmark`
11. `Privacy-safe aggregate handoff`

圖旁短註明：Official test 沒有 public masks，因此不呈現 quantitative official-test metrics；缺少 patient ID，因此不宣稱 patient-wise split。

## 6. Diagram 3 — Local Review Sequence

### 回答的問題

「使用者從開啟頁面到取得 Overlay／Mask，系統實際做了什麼？」

### Participants

- `使用者`
- `React 複核工作台`
- `FastAPI`
- `ONNX 推論層`

### Sequence

1. 頁面載入後，React 呼叫 `GET /api/model-status`。
2. FastAPI 回傳 `local_review ready`；artifact 缺失時的 showcase 行為由圖前 prose 說明，不與主流程塞在同一張 sequence diagram。
3. 使用者選擇 PNG／JPEG／WebP；React 在 client 端檢查 MIME 與 12 MiB 上限，只建立 local preview，不自動推論。
4. 使用者明確按下「開始分割複核」後，React 才送出 `POST /api/predict`。
5. FastAPI 驗證 content type、payload size、decode 與最大 dimension，再把已驗證影像交給 ONNX 推論層。
6. ONNX 推論層使用 private ONNX／calibration，回傳 mask、ratio、confidence、provider 與 inference time。
7. FastAPI 回傳 sanitized review response；React 顯示 Original／Overlay／Mask 與人工複核提示。

Sequence note 明確標示：API 不保存原始檔名、不建立 gallery；confidence 是模型分割信心，不是臨床信心。錯誤分支只顯示 sanitized message，不回傳內部 exception。

## 7. 視覺與可讀性

- 三張 Mermaid 的 `themeVariables.fontSize` 統一提高為 22px；同時減少節點、lifeline 與訊息長度，避免 GitHub 因整圖過寬而把 22px 再縮成不可讀小字。
- Sequence diagram 移除 autonumber、只保留四條 lifeline 與本機複核 happy path；showcase 分支移至圖前 prose，避免一張圖同時承擔狀態機與 API sequence。
- class definitions 可保留 `stroke-width`／`stroke-dasharray` 等非色彩語意；不得固定 `fill`、foreground `color`、`lineColor` 或 sequence signal colors，讓 GitHub light／dark theme 自動提供可讀對比。
- Public、process、private、evidence 使用不同 class；private artifact 使用虛線 border，並標記「不隨 repository 發布」。
- 避免在節點中放長句、SHA、完整路徑或大量 metrics；精確數字留在結果表與 prose。
- 每張圖前有一行用途說明，圖後有 2–3 點閱讀提示，讓 Mermaid 無法顯示時仍可理解重點。

## 8. 驗證與完成條件

- 三張 Mermaid 圖均通過 syntax validation，且在 GitHub-compatible Mermaid renderer 產生 SVG／PNG preview。
- 人工檢視 desktop 與窄寬度 preview：無節點文字截斷、交叉線難以追蹤或小於可讀字級的內容；在 823px GitHub README content width 下，三張圖的投影文字不得因 viewBox 縮放低於 16px。
- README local links、results markers、release links與現有 metadata regressions 全部通過。
- Repository privacy audit 必須維持 0 violations；不得新增 medical image、mask、weight、ONNX 或 private artifact。
- 完整 Python suite、Ruff、format 與 `git diff --check` 通過；README-only change 不需要重跑 GPU、training 或 model inference。
- 更新 `PROGRESS.md`，記錄圖解範圍、Mermaid validation、README render review、privacy boundary 與測試證據。

## 9. 非目標

- 不建立新的 live demo、hosting、model repository 或 FUSeg permission workflow。
- 不製作 Deployment、CI/CD、class diagram 或 database diagram；這些會重複現有資訊或增加一般訪客負擔。
- 不改 scientific protocol、正式結果、模型、API schema、runtime behavior 或 release version。
- 不為了視覺效果加入未執行的 cloud infrastructure、database、queue、monitoring 或 security service。
