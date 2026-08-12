# WoundScope 傷口分割複核工作台設計規格

> 日期：2026-08-13
> 狀態：Approved direction／implementation pending
> 範圍：code-only UI patch；不修改 scientific protocol、正式 metrics、model family、calibration 規則或公開 artifact policy

## 1. 目標

將現有單頁 Gradio demo 升級為作品級「傷口分割複核工作台」，讓 GitHub 訪客即使沒有 private model artifacts，也能理解 WoundScope 的研究方法、工程完整度、安全邊界與部署狀態；本機具備合法 ONNX／calibration artifacts 時，才開啟影像上傳與 segmentation 複核功能。

成功條件：

- 人讀內容以正體中文（zh-TW）為主，technical proper nouns 保留原文。
- 一進頁面即可辨識「研究型 medical CV segmentation」定位，不像套件預設 demo。
- 以舒適閱讀為優先：desktop body font 至少 17px、行高至少 1.55、互動目標至少 44×44px。
- 空間緊湊但不壓迫；不使用巨大 hero、無效留白、重複卡片或過深層級。
- 沒有 model artifact 時仍是完整且可信的研究展示，不呈現壞掉的推論表單。
- 有 model artifact 時提供 image comparison、overlay opacity、mask toggle、ratio、confidence、latency、review warning 與 provenance。
- 不顯示 diagnosis、severity、prognosis 或 treatment recommendation。
- 不公開或提交 FUSeg images／masks、weights、ONNX、image-level manifests、private galleries 或 secrets。

## 2. 技術方向

採用 React + TypeScript + Vite 作為 frontend，FastAPI 作為 Python API 與 static frontend host。

選擇理由：

- React 能建立細緻的影像比較與狀態互動，明顯區隔現有 Gradio／Streamlit 作品。
- TypeScript 讓 API contract、model availability 與 error states 可被編譯期檢查。
- Vite 提供小型、快速且容易驗證的 SPA build，不引入 Next.js server runtime。
- FastAPI 保留現有 `woundscope` Python inference 邏輯，避免在 frontend 重寫 preprocessing、calibration 或 confidence。
- production 使用 multi-stage Docker build：Node 只負責產生 static assets，runtime 仍為 Python CPU image。

不採用：

- Jinja／HTMX：bundle 較小，但 image compare、overlay controls 與 async state 的可維護性較差。
- NiceGUI／Panel：Python-only 便利，但仍容易帶出 framework-default 視覺，不符合 portfolio differentiation。
- Next.js：本專案不需要 SSR、RSC 或額外 Node runtime；增加的部署複雜度沒有足夠回報。

## 3. 產品模式與權限邊界

### 3.1 Research showcase mode

當 ONNX 不存在或 calibration 不完整時預設進入此模式：

- 顯示 verified official-validation aggregate、研究流程與 artifact provenance 摘要。
- 顯示 model-backed inference 尚未啟用的明確狀態，不將其包裝成 service outage。
- 主視覺使用抽象的 segmentation contour／grid 圖形與 synthetic fixture；不得使用 FUSeg 或臆造 clinical result。
- inference controls 維持不可用，並解釋權限與本機 artifact 條件。
- 提供 GitHub source、MODEL_CARD、DATA_CARD 與 result release 的導覽入口。

### 3.2 Local review mode

只有 backend 確認本機 ONNX 存在且可安全初始化時啟用：

- 接受單張本機上傳圖片，禁止 webcam、clipboard URL 與 remote URL source。
- 圖片只在 request memory 與 browser object URL 中處理，不寫入 repository 或 application log。
- 回傳原圖顯示、overlay、binary mask、wound pixel ratio、model segmentation confidence、inference latency 與人工複核警示。
- calibration 缺失或不相容時，依既有 inference contract 顯示低信心／人工複核狀態，不靜默降級為可信結果。
- 錯誤訊息不得暴露 private artifact path、token、原始檔名或 stack trace。

## 4. 資訊架構

頁面維持單一工作台，不新增多層 routing。

1. Compact header
   - WoundScope wordmark
   - `Research prototype`、`Code-only`／`Local model ready` status
   - GitHub、研究文件與 theme controls
2. Evidence strip
   - verified U-Net Dice、official validation sample count、model families、release version
   - 每個數據都帶精準 scope label，不讓讀者誤認為 official-test 或 clinical performance
3. Review workspace
   - 左欄：privacy notice、upload／replace、run action、model readiness
   - 右欄：image stage；empty、loading、result、error 四種狀態共用固定尺寸，避免 layout shift
4. Result rail
   - wound pixel ratio、model confidence、latency、review state
   - confidence 明示「模型分割信心，非臨床信心」
5. Evidence and provenance
   - default 顯示精簡摘要
   - disclosure 展開 calibration、model／artifact hash prefix、runtime provider、source release
6. Safety footer
   - 非臨床用途、人工複核、PHI 與 FUSeg attribution

Desktop 使用 12-column grid：control pane 4 columns、visual stage 8 columns。Tablet 轉為 5/7 或上下排列；mobile 單欄，result metrics 改為 2×2 grid。Header、evidence strip 與 safety copy 不重複。

## 5. 視覺系統

概念名稱：`Clinical Editorial／沉靜研究室`。

### 5.1 色彩

- Canvas：暖象牙 `#F4F1EA`
- Surface：柔白 `#FBFAF7`
- Ink：深藍灰 `#24313A`
- Muted ink：石板灰 `#5E6A6F`
- Primary：鼠尾草綠 `#667F73`
- Secondary：霧藍 `#8EA6AF`
- Accent：低飽和陶土 `#C77862`
- Review warning：赭黃 `#B9823D`
- Success：深苔綠 `#4E7562`

所有語意色使用 CSS custom properties；文字與背景對比至少符合 WCAG AA 4.5:1。陶土色只用於主要 action、mask contour 與少量視覺焦點，不形成紅色警報感。

### 5.2 Typography

- 中文正文：`Noto Sans TC` 優先，後接 `PingFang TC`、`Microsoft JhengHei` 與 sans-serif fallback。
- 品牌／大數字：`Noto Serif TC` 優先，後接適當 serif fallback。
- Body：17px／1.65；secondary copy 不低於 15px。
- Button、label：16px 以上；verified metric 數字 28–36px。
- 不以全大寫英文作主要導覽；technical tokens 可使用 monospace。

### 5.3 Shape and depth

- 8px spacing grid；主要 section gap 24–32px、card padding 20–24px。
- Radius 14–18px，避免每一層都包成卡片。
- 使用 1px 淡色 border、局部 inset highlight 與單層柔和 shadow。
- 背景加入極淡的 medical-grid／contour pattern，opacity 不高於 4%。
- Icon 使用 Lucide SVG；不使用 emoji、圖片式 icon 或無 label 的 icon-only controls。

### 5.4 Motion

- 初次載入只做一次 180–260ms stagger reveal。
- overlay slider、toggle 與 status transition 使用 150–220ms easing。
- loading state 使用 mask contour sweep，不使用無意義 spinner 牆。
- 完整支援 `prefers-reduced-motion`；禁止持續漂浮與裝飾性 parallax。

## 6. 核心互動

### 6.1 Upload

- Dropzone 與 button 都可由 keyboard 操作；drag state、focus state 與 invalid state 明確。
- 只允許 backend 支援的 raster formats，先做 browser-side size/type feedback，再由 backend 驗證。
- 上傳後先顯示 local preview，使用者按「開始分割複核」才送出。
- 更換影像會清除前一筆 prediction、object URL 與 stale error。

### 6.2 Image review

- 預設顯示 overlay，使用 before/after comparison slider 直接比較 original 與 overlay。
- 提供 `原圖`、`Overlay`、`Mask` 三種 view toggle。
- Overlay opacity 範圍 20–80%，預設 45%；label 與數值同步可見。
- Fullscreen 保留相同 controls 與 keyboard operation。
- Mask 不只靠顏色：使用 contour stroke + translucent fill，兼顧 color-vision accessibility。

### 6.3 Results

- Ratio 是 geometry summary，不描述 severity。
- Confidence 同時顯示 percentage、calibration availability 與 low-confidence reason。
- Review state 使用文字、icon 與色彩三重編碼。
- Latency 標示 device/provider，避免與 model quality 混淆。

## 7. API contract

### `GET /api/health`

回傳 application version 與 service status，不載入 model。

### `GET /api/model-status`

回傳：

- `mode`: `showcase | local_review`
- `model_available`
- `calibration_available`
- safe model label／hash prefix
- provider (`CPUExecutionProvider` 等)
- public-safe readiness message

不得回傳 absolute path、HF token、private repository ID 或完整 secret-bearing exception。

### `POST /api/predict`

- multipart 單檔 input；限制 MIME、decoded dimensions 與 request size。
- 使用現有 predictor 與 calibration contract。
- 回傳 overlay／mask 的 in-memory encoded assets，以及 ratio、confidence、latency、review reasons 與 safe provenance。
- model unavailable 回 `503 MODEL_NOT_AVAILABLE`；input invalid 回 `422 INVALID_IMAGE`；internal inference failure 回 sanitized `500 INFERENCE_FAILED`。

Frontend 使用 discriminated union 對 success／known error 建模，不以任意字串推測狀態。

## 8. 程式邊界

```text
frontend/
├── src/
│   ├── app/
│   ├── components/
│   ├── features/review/
│   ├── lib/api/
│   ├── styles/
│   └── test/
├── package.json
├── tsconfig.json
└── vite.config.ts

src/woundscope/
├── api.py                 # FastAPI factory and sanitized HTTP boundary
├── demo.py                # existing presentation-independent result formatting
├── gradio_app.py          # compatibility surface; no longer primary UI
└── inference.py           # unchanged scientific inference contract

app/app.py                 # primary FastAPI entry point
```

Frontend 不實作 segmentation、threshold、calibration 或 clinical interpretation。Backend 不包含 React layout knowledge。API schemas 是兩者唯一 contract。

## 9. Testing

所有 behavior changes 遵循 RED → GREEN → REFACTOR。

Backend：

- model status 在 artifacts available／missing／invalid 三種狀態正確且不洩漏路徑。
- upload validation、model-unavailable 503、sanitized inference failure。
- synthetic predictor end-to-end response schema、overlay／mask dimensions 與 existing result semantics。
- Gradio compatibility smoke 在 transition period 保留。

Frontend：

- TypeScript typecheck、ESLint、Vitest + Testing Library。
- showcase／local-ready／loading／result／error states。
- keyboard upload、view toggle、opacity control、error recovery。
- axe accessibility checks；focus order 與 visible focus manual verification。

Browser：

- Playwright desktop 1440×900、tablet 1024×768、mobile 390×844。
- 無 horizontal scroll、無 clipped text、body font 與 tap target gate。
- synthetic fixture result flow；不使用或生成 medical image artifact。
- light/dark contrast、reduced-motion 與 error state visual inspection。

Repository gate：

- Python Ruff、format、full pytest、`git diff --check`、repository privacy audit。
- Frontend install lock、lint、typecheck、unit tests、production build。
- Docker build 與 no-model startup smoke；model-backed smoke 只使用 synthetic predictor injection。

## 10. Documentation and portfolio presentation

- README 加入一張 synthetic／artifact-free UI screenshot，明確標示為介面展示而非 clinical prediction。
- README 保留正體中文主敘事，新增 frontend／API 架構與本機啟動方式。
- screenshot 不含 FUSeg image、mask、private path、filename、artifact hash full value 或 user data。
- GitHub 首屏應先看到 concise project value、verified aggregate、UI screenshot 與 Colab/source actions；不把安裝長文放在 hero。
- 不建立 model-backed public Space，不發布 weights／ONNX；release 版本另由後續 release plan 決定。

## 11. Delivery boundaries

本次包含：

- 新 React/Vite frontend、FastAPI boundary、primary local app entry、responsive UI、synthetic tests、Docker integration、README screenshot／usage update。
- 保留既有 inference、calibration、confidence 與 metrics semantics。

本次不包含：

- scientific retraining、new metrics、threshold tuning、diagnosis／severity features。
- FUSeg data redistribution、weight／ONNX publication、model-backed hosted deployment。
- authentication、database、multi-user history、case persistence、PDF clinical report 或 DICOM/PACS integration。

## 12. Acceptance criteria

- 首頁在沒有 model 時可完整載入，明確呈現 showcase mode，無 broken controls。
- local model ready 時可完成 upload → inference → compare → review 的單次流程。
- 核心操作在 390px、1024px、1440px viewport 可讀可用；無小於規格的主要文字與互動目標。
- 所有 medical scope、privacy、permission 與 provenance guardrails 維持成立。
- Python、frontend、browser、Docker 與 repository privacy gates 有 fresh PASS evidence。
- branch 僅包含 UI patch 與必要文件；不含 data、weights、ONNX、gallery、secret 或 scientific claim 變更。
