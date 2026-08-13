# WoundScope Scientific Console 視覺精簡規格

> 日期：2026-08-13
> 狀態：已核准，待實作
> 範圍：只調整 React showcase／review workbench 的 typography、spacing、shape 與資訊層級；不修改 scientific protocol、正式 metrics、model behavior 或 artifact policy

## 1. 問題與目標

目前首頁的 serif 超大主標、宣傳式斷句與大面積 Hero 容易被理解為新聞／品牌 landing page；同時，15px 次要文字、510px 示意板、重複外框與大圓角降低了研究工具應有的資訊密度。

本次將視覺方向由 `Clinical Editorial／沉靜研究室` 收斂為 `Scientific Console／理性研究台`：保留暖象牙、鼠尾草與霧藍 palette，但讓 typography、對齊、分隔線與資料標籤承擔層級，減少卡片、陰影和裝飾性留白。

核心目的只有一個：讓訪客在第一個 viewport 內快速辨識 WoundScope 是具備 verified evidence、provenance 與 safety boundaries 的 medical CV segmentation research workbench。

## 2. 核准方向與取捨

採用方案 A：`Scientific Console`。

- 不採 `Clinical Report`：仍會保留較強 editorial／出版物氣質，無法充分解決「像新聞標題」。
- 不採 `Technical Dashboard`：雖然密度最高，但容易變成一般後台管理介面，削弱研究展示的辨識度。
- 保留既有功能、verified copy、abstract contour illustration、light／dark theme 與 responsive behavior；本次只做精準 refinement，不新增功能。

## 3. Typography

### 3.1 Showcase mode

- H1 固定為「WoundScope 傷口分割複核工作台」，不再使用口號式斷句。
- H1 使用 `Noto Sans TC` 系列，不使用 serif；desktop 34–36px、tablet 32–34px、mobile 28–30px，line-height 1.2，font-weight 650–700。
- H1 下方以一段 17–18px 說明研究工作流；不使用超過兩行的行銷文案。
- 不在 H1 上方放 kicker；`Medical Computer Vision` 與 `Research prototype` 作為 H1 說明後的 16px research metadata。
- 一般正文 desktop 18px、mobile 17px；次要資訊與 metadata 不低於 16px。
- Metric numeral 可保留 serif 或 tabular numerals，但 section heading、status 與 controls 一律使用 sans-serif。

### 3.2 Local review mode

- 工作台 H1 同樣使用 sans-serif，desktop 不超過 36px、mobile 不超過 30px。
- 結果數值維持清楚的 tabular hierarchy；confidence 仍固定標示為模型分割信心，非臨床信心。

## 4. Layout 與空間

- Desktop 首屏維持左右分欄，但 copy 欄改為上對齊的研究摘要，不再垂直置中製造大片空白。
- Main top padding 收斂至 24–32px；section gap 由 24px 收斂至 16–20px。
- Abstract research plate 的 desktop min-height 由 510px 降至 360–390px；SVG 高度同步降低，保留可辨識的量測平面。
- Mode status 從獨立 card 改為 inline status row，直接接在研究摘要下方。
- 研究證據在 desktop 第一個 viewport 內可見；不要求使用者先捲過完整 Hero。
- Evidence 與 provenance 使用 full-width information rails；標題欄、數據欄與細分隔線建立結構，不額外套外層 card。
- Mobile 仍為單欄；Research plate 保留在文字後方，但高度不超過約 300px，避免首屏只看到 Hero。

## 5. Shape、border 與 depth

- 全站圓角 token 收斂為：small 4px、medium 6px、large 8px。
- 只在以下真正需要邊界的互動／量測面保留完整外框：research plate、upload dropzone、image canvas、fullscreen stage、主要 action。
- Header、mode status、evidence strip、provenance、footer 不使用 card background、shadow 或大圓角。
- Evidence 與 provenance 只使用 section top/bottom rule 與 column dividers。
- Research plate 移除 inset 雙框與主 shadow，改為單一 1px border；視覺焦點由 contour、grid 與資料標籤承擔。
- Pills 只保留給二元狀態、segmented control 或真正的 compact badge；一般 navigation、status copy 與 action 不預設使用 pill。
- 不建立 card inside card；若 spacing、heading 或 divider 已能表達分組，就不加外框。

## 6. Content hierarchy

Showcase 首屏順序固定為：

1. H1：產品／工具名稱。
2. 一句研究工作流說明。
3. Research metadata：研究領域與 prototype scope。
4. Inline mode status：code-only／local model readiness 與安全說明。
5. DATA_CARD／provenance 兩個 secondary links。
6. Abstract research plate。
7. Verified evidence rail。

Provenance section 標題改為直接、技術性的敘述，例如「Artifact 與研究來源」，不使用「每個結果，都必須知道從哪裡來」這類口號句。既有 release、artifact、calibration 與 permission 四個事實維持不變。

## 7. Responsive 與 accessibility

- 1440×900、1024×768、390×844 與 375px viewport 不得有 horizontal overflow。
- Desktop body text 18px；mobile body text 17px；任何可見輔助文字不得低於 16px。
- 互動目標仍至少 44×44px；移除 pill／card 不得縮小 hit target。
- Focus ring、skip link、semantic headings、`aria-live` scope 與 reduced-motion behavior 維持既有 contract。
- Light／dark theme 都必須以 divider、type weight 與 contrast 保持層級，不能只依賴淡色 surface card。

## 8. TDD 與驗證

在 production code 前新增 regression tests，至少驗證：

- Showcase H1 為「WoundScope 傷口分割複核工作台」，且舊口號不存在。
- Provenance 使用直接技術標題，既有四個事實與 safety copy 未被移除。
- Status、evidence、provenance 的 semantic structure 仍可由 role／heading／definition list 查得。

實作後執行：

- Frontend Vitest、TypeScript typecheck、ESLint、Vite production build。
- Python Ruff、format、full pytest、repository privacy audit、`git diff --check`。
- Impeccable detector 對本次 changed targets 執行一次。
- Browser 以 desktop／tablet／mobile 與 light／dark 做一次 batched inspection；必要修正後最多再確認一次。
- 檢查最小可見字級、overflow、tap targets、console errors 與首屏 evidence 可見性。

## 9. 非範圍與安全邊界

- 不修改 verified aggregate、formal result、model family、loss、calibration、threshold、confidence semantics 或 medical scope。
- 不加入 diagnosis、severity、prognosis、treatment advice 或臨床 claim。
- 不使用 FUSeg image／mask、private filename／path、weights、ONNX、gallery、secret 或 image-level artifact。
- 不 push、部署、訓練或發布 model-backed Space；`PERMISSION_PENDING` 維持不變。

## 10. 驗收條件

- 首頁不再呈現新聞／宣傳式大標，而像理性、可操作的研究介面。
- 主標明顯縮小、正文與 metadata 明顯放大，字級層級可一眼辨識。
- 1440×900 第一個 viewport 可同時看到研究摘要、主要示意面與 verified evidence 的起始內容。
- 不必要 card、shadow、nested border 與大圓角已移除；保留的外框都有明確功能。
- 所有既有功能、安全聲明、provenance 與 responsive/accessibility contract 維持完整。
