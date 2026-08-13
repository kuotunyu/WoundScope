# WoundScope 直覺使用導引設計規格

> 日期：2026-08-13
> 狀態：已完成並合併至 `main`
> 範圍：改善 code-only showcase 與 local review 的操作理解；不修改模型、inference、scientific protocol、結果或 artifact permission

## 1. 問題與成功條件

目前介面已能清楚呈現 WoundScope 的研究品質，但訪客仍需自行推論「為什麼沒有 upload form」以及「如何從 showcase 進入真正的本機複核」。README 已有完整啟動方式，頁面內卻缺少連接目前狀態、下一步與實際操作的導引。

本次成功條件如下：

- code-only 訪客在第一個 viewport 內理解目前不能執行 inference 的原因。
- 訪客能在約十秒內辨識本機啟用與實際複核的三個主要步驟。
- 有一個與目前狀態相符的主要 CTA，直接前往 README 的本機啟用章節。
- local review 使用者在 upload 前就知道「選擇影像不等於提交」，並理解結果需要人工複核。
- 不使用 disabled upload、假 prediction 或 synthetic medical case 暗示公開服務已可推論。
- 不增加卡片堆疊、大圓角、過小輔助文字或無效留白。

## 2. 方案比較與選擇

### 方案 A：情境式三步驟導引（採用）

在既有模式狀態下方加入緊湊的流程線。Showcase 顯示「準備 artifacts → 啟動本機工作台 → 上傳並人工複核」；local review 顯示「選擇影像 → 明確開始分割 → 比較圖層並人工複核」。Showcase 的唯一主要 CTA 是「查看本機啟用方式」。

優點是就地回答使用者問題、無假功能、可維持首屏資訊密度，也能沿用既有 scientific console 的 rule／divider 語言。缺點是需要為兩種模式各維護一組精簡文案。

### 方案 B：互動式 onboarding 或 walkthrough

首次進站用 overlay、modal 或逐步 spotlight 說明介面。它能帶領操作，但 code-only 模式沒有可操作的 upload，容易形成教學與能力不一致；也會增加狀態管理、關閉行為與 accessibility 負擔。本階段不採用。

### 方案 C：公開 synthetic demo

提供合成影像與固定結果，讓訪客操作 Overlay／Mask 控制。展示性最強，但需要額外建立不會被誤解為真實 prediction 的資料與標示，且偏離「教使用者如何啟用自己的 local artifacts」這個當前問題。本階段不採用，未來可獨立評估。

## 3. 資訊架構

### 3.1 Showcase mode

既有順序調整為：

1. 研究名稱與一句工作流說明。
2. `研究展示模式` 狀態：明確說明目前是 code-only，model artifact 未公開，因此頁面不顯示 upload form。
3. `使用流程` 三步驟：
   - `01 準備 artifacts`：在自己的機器準備 private ONNX 與 calibration metadata。
   - `02 啟動本機工作台`：設定環境變數並啟動 FastAPI／React bundle。
   - `03 上傳並複核`：上傳影像、明確執行 segmentation、比較 Original／Overlay／Mask，再由專業人員人工確認。
4. 主要 CTA `查看本機啟用方式`，前往 GitHub README 的 `啟動分割複核工作台` anchor。
5. 次要文字連結 `查看資料治理` 與 `檢視 provenance`。

三步驟導引在 desktop 置於雙欄摘要與 research plate 下方的跨欄流程帶，避免窄欄換行與右側無效空白；mobile 則排在摘要與 research plate 之間。導引使用單一上方分隔線與序號，不建立三張獨立卡片。抽象 Segmentation 複核平面維持純研究示意，不塞入操作說明。

### 3.2 Local review mode

在 workspace intro 與 upload console 之間加入一列 `操作流程`：

1. `選擇影像`：PNG／JPEG／WebP，檔案限制沿用現有驗證。
2. `明確開始分割`：只有按下主要 action 才傳送到本機 API。
3. `比較並人工複核`：檢視 Original／Overlay／Mask、confidence 與 review reasons。

流程列是持續可見的使用提示，不做複雜 wizard。現有 field message、loading state、error state 與 result state 繼續提供 just-in-time feedback；不重複相同長句。

## 4. 元件與責任

新增一個無狀態的 `WorkflowGuide` presentation component：

- 輸入 `variant: "showcase" | "review"`。
- 輸出有可讀 heading 的 ordered list。
- `showcase` variant 額外輸出 README CTA；`review` variant 不建立外部導覽。
- 不讀取 model、API 或 session state，不自行判斷 permission。

`ResearchShowcase` 負責提供 code-only 的狀態語境並放置 showcase variant。`ReviewWorkspace` 負責放置 review variant。API、review session hook 與 inference response 不變。

## 5. 視覺與互動規則

- 維持 `Scientific Console／理性研究台`，以 typography、序號與細分隔線形成層級。
- 流程在 desktop 為三欄；狹窄 viewport 改為單欄或緊湊縱向列表。
- 不為每個步驟增加完整 border、surface card、shadow 或大圓角。
- `01／02／03` 使用既有 monospace／tabular numeral 語言；步驟標題至少 16px，說明至少 16px。
- Showcase CTA 使用單一 primary action 樣式，但不寫「立即推論」或其他超出可用能力的字樣。
- CTA hit target 至少 44px，focus-visible 清楚；ordered list 保留 semantic sequence。
- 新增內容不得使 1440×900 首屏完全看不到 verified evidence；必要時優先精簡重複文案與垂直間距，而不是縮小字體。

## 6. 狀態、錯誤與安全語意

- Model status 讀取成功但不可用：直接說明 code-only 與 upload 未開放。
- Model status API 失敗：保留現有服務錯誤訊息；導引仍可顯示，讓使用者能前往 README 排查本機啟動。
- Local model ready：不顯示 setup CTA，改顯示實際操作三步驟。
- File validation、request error、loading 與 result handling 完全沿用既有行為。
- `confidence` 固定稱為模型分割信心，不是臨床信心。
- 不宣稱 diagnosis、severity、prognosis、treatment advice、official-test performance 或 patient-wise split。
- `PERMISSION_PENDING` 不變；不發布 weights、ONNX、FUSeg image／mask 或 image-level artifact。

## 7. 測試與驗收

實作採 RED → GREEN → REFACTOR，先新增會失敗的 semantic tests：

- Showcase 能找到 `使用流程` ordered list、三個指定步驟與 `查看本機啟用方式` link。
- CTA 指向 README 的本機啟用 anchor，不指向 model download 或公開 inference。
- Showcase 不出現 disabled file input 或「立即推論」字樣。
- Local review 能找到 `操作流程` ordered list，並清楚出現「明確開始分割」與「人工複核」。
- 既有 model status、upload、explicit submit、result、accessibility 與 privacy tests 全部維持通過。

完成後執行 frontend test、typecheck、lint、production build，並跑完整 Python／privacy gate。瀏覽器至少檢查 1440×900、1024×768、390×844 的 light／dark、horizontal overflow、最小字級、44px target、首屏 evidence 可見性與 console errors。

## 8. 非範圍

- 不製作 modal tour、stepper state machine、教學影片或 synthetic medical demo。
- 不修改 API schema、inference pipeline、檔案限制、模型狀態判斷或 artifact path。
- 不修改 verified metrics、research claims、Model Card、Data Card 或 scientific protocol。
- 不 merge、push、部署、訓練或公開任何 private artifact；後續 GitHub 外部動作仍需使用者明確授權。
