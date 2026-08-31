# WoundScope Static GitHub Pages 設計規格

> 日期：2026-08-31（Asia/Taipei）
> 狀態：設計已經中央核准；本文只定義 implementation contract，不授權 deploy、GitHub Pages activation、About metadata 修改或 Hugging Face 操作。
> 規範詞價詞語：「必須」是 blocking acceptance criterion；「可」代表在不擴張公開邊界時的選擇性行為。

## 1. 決策摘要

WoundScope 首版 website 固定為 `https://kuotunyu.github.io/WoundScope/` 下的單頁、`zh-TW`-first、aggregate-only research showcase。它是靜態文件集，不是簡化版 inference app，也不是既有 React／FastAPI review workbench 的 deployment mode。

首版採用 **zero-runtime-JavaScript** 架構：建置期從已鎖定的 Git objects 投影 evidence，產生語意化 HTML、一份 same-origin CSS、已批准的 aggregate SVG、license／NOTICE／SBOM 與 provenance manifest。瀏覽器不執行 React、API client、upload、inference、model status 或 model download 程式碼。

這個架構有三個目的：

1. 把既有 workbench 的視覺語言與 research hierarchy 安全投影為 portfolio page；
2. 用構建期驗證代替手抄 metric，將 scientific evidence 與 site source 的 provenance 分離；
3. 使「沒有上傳、API、模型、外部 runtime request」成為可機器驗證的 fail-closed contract，不只是文案承諾。

## 2. 已驗證基線與 Git object locks

本設計以下列 immutable identifiers 為準：

| 用途 | 已驗證值 |
|---|---|
| Site code base | remote `main` exact commit `b6f23032d0d55e7442b43724cb059ba67198d3c8` |
| Evidence release | annotated tag `v0.2.2` |
| Evidence tag object | `1f51e659f0aeba9e2d249d7f42dae2ba57cd1cc4` |
| Evidence peeled commit | `1b3df3b516cc4d366dc9da3cb01e8d0a319be613` |
| Evidence README blob | `f5b8dd4681738aa372072cac9c827478d13c1f68` |
| Evidence DATA_CARD blob | `2b7fe52ac9784c9c2682300d2bd56bb72b20d19c` |
| Evidence MODEL_CARD blob | `c93a99579ad1b4fb1d03b0a6e15ba8300287ca9c` |
| Aggregate SVG Git blob | `28d91ba5f6fb61d1114106e7519007d6aeb5d6b8` |
| Aggregate SVG bytes | `3009` |
| Aggregate SVG SHA-256 | `1eafa7c35b06928b6cfc2910326f9c0adaf88098ab3a734ba43e16914fd7814d` |

這些值已以 local Git object database、`git ls-remote` 與 remote metadata 交叉核對。`v0.2.2` 必須仍是 annotated tag，且 tag object 與 peeled commit 必須同時相符；只比對 tag 名稱或 README 文字不足以通過。

Site build 必須顯示兩組分開的 provenance：

- **Site source**：build 當下的 full 40-character `GITHUB_SHA` 或等價 local commit SHA。
- **Evidence source**：`v0.2.2`、tag object 與 peeled evidence commit。

Site source 不得被稱為 training source 或 evidence source；site artifact tree digest 也不得反向當作 model-result provenance。

## 3. Stale governance 與 path handling

Repo-local `AGENTS.md` 尚包含已不存在的 legacy C-drive canonical path，且仍將 `v0.2.1` 稱為 current release。中央決策已對本設計階段做出書面 override：

- 本階段以 `git rev-parse --show-toplevel` 在已批准 D-drive workspace 回報的 repository root 為 canonical checkout。
- 不建立新 clone；只使用中央明確授權的 isolated worktree。
- 任何 script、test、manifest 或文件都不得寫死 machine-local absolute path。

未來 implementation 的 **Task 0** 必須在任何 app-source、site-source 或 workflow 變更前，先另行同步：

1. `AGENTS.md` 的 canonical path 發現方式、current release 與 static-site decision；
2. `PROJECT_PLAN.md` Decision Log 的 Pages-only material publication decision；
3. `PROGRESS.md` 的 current milestone、gate、branch／worktree 與驗證證據。

上述三個 local governance files 是 ignored／private local-control artifacts，不得進入 public site、CI review artifact 或 app-source scope。是否 commit 必須遵循它們既有的 local governance policy；依目前 policy 預期不 commit，也不得用 `git add -f` 強行納入公開歷史。若它們在 implementation Task 0 後仍與中央決策衝突，implementation 必須 fail closed。

## 4. 目標與 non-goals

### 4.1 目標

- 建立一個 `zh-TW`-first 單頁 research showcase。
- 呈現 WoundScope 的 data governance、reproducible workflow、aggregate evidence、limitations 與 artifact boundary。
- 在不使用 medical image 或 sample prediction 的前提下，重用 Scientific Console 的排版、色彩、密度與 abstract contour 語言。
- 讓網頁 evidence 從 immutable release Git objects 自動投影。
- 對 privacy、license、accessibility、browser、subpath 與 deterministic build 建立可重播 gates。
- 在未啟用 Pages 前產生可下載人工審閱的 CI review artifact。

### 4.2 永久 non-goals

- Upload、camera、drag-and-drop、file input 或任何使用者影像處理。
- API、FastAPI、Gradio、WebSocket、serverless function 或 backend runtime。
- Inference、model status、confidence calculation、model download、artifact download 或 Hugging Face runtime。
- FUSeg images／masks、medical images、sample predictions、error galleries 或 synthetic wound-like raster。
- Checkpoints、weights、ONNX、calibration 或 image-level results。
- Analytics、telemetry、cookies、tracking pixel、remote fonts、CDN script、comments、forms、search service 或 service worker。
- 臨床診斷、嚴重度、預後、治療、triage、medical-device 或 patient-safety claim。
- 本 spec 不啟用 GitHub Pages、不新增 deploy permissions，不改 GitHub About／homepage，不操作 HF。

## 5. 公開科學與醫療 claim ceiling

頁面可說：

- WoundScope 是 foot-ulcer binary semantic segmentation 的 research and engineering showcase。
- 公開頁面展示 code、methodology、aggregate evidence 與 reproducibility controls，不提供模型。
- U-Net 與 SegFormer-B0 數值是鎖定 FUSeg Official Validation 200 張上的 observed results，每架構為 seeds 42／43／44。
- Dice CI 是 2,000 次 image-level percentile Bootstrap；無 patient ID，無法校正同一病患多張影像的相關性。
- 結果不是 official-test、external、multi-center 或 clinical performance。
- 任何 model confidence 概念只是 segmentation-review signal，不是臨床信心。首版網站本身不計算或顯示個別 prediction confidence。

頁面不得說：

- patient-wise split、official-test score、臨床驗證、幾乎可用於診斷或治療。
- 「準確率 85%」、「辨識傷口嚴重度」、「即時分析」、「臨床工作台」、「production-ready deployment」或「live demo」。
- 高分數代表較好治療、安全性或跨機構 generalization。
- Apache-2.0 覆蓋 FUSeg、pretrained weights 或 derived model artifacts。

所有首屏、evidence section、SVG caption 與 footer 都必須在不展開 details 的情況下看得到「研究用、非 official-test、非臨床效能」界線。

## 6. 頁面資訊架構

頁面保持單一 URL 與 anchor navigation，不引入 client router。順序固定為：

1. **Header**：WoundScope wordmark、「Static research showcase」狀態、頁內 navigation 與 GitHub repository link。
2. **Research overview**：一個 H1、短述、研究免責與 abstract contour SVG。輪廓必須標示為 interface illustration，並從 accessibility tree 中隱藏其純裝飾圖形。
3. **Verified aggregate evidence**：先放 semantic HTML table，再放字節驗證過的 aggregate SVG 與 caption。
4. **Reproducible workflow**：只說明 data integrity、locked experiment、aggregate handoff；不提供執行按鈕。
5. **Provenance and boundaries**：分開顯示 site SHA、evidence release／evidence SHA、FUSeg revision、code/data/artifact 公開邊界。
6. **Limitations, attribution and license**：patient-ID、source correlation、single-source、official-test mask、license 與 non-clinical limitations。
7. **Footer**：公開文件、release、citation、repository license 與 third-party notices links。

## 7. Static entry architecture

### 7.1 獨立 source boundary

未來 implementation 應使用獨立 `site/` source tree，並以單一 build orchestrator 產生靜態 artifact。預期單元邊界如下：

```text
site/
├── index.template.html        # 無 metrics；只含已核准的 zh-TW copy slots
├── 404.template.html
├── site.css                   # WoundScope-authored, no @import/remote url
└── links.allowlist.json       # exact external-navigation allowlist
scripts/
├── build_pages_site.py        # stdlib-only evidence projector + static builder
└── audit_pages_site.py        # exact inventory/content/network/license audit
tests/
└── pages/                      # Git-object, bundle, claims, a11y/browser contracts
```

檔名可在 implementation plan 中依現有命名慣例做小幅度調整，但以下 dependency direction 不得改變：

```text
immutable Git evidence objects
          │
          ▼
stdlib-only evidence projector ──► typed public evidence model
          │                                │
          └── exact SVG bytes             ▼
                                   static HTML renderer
authored template + CSS ─────────────┘
                                            │
                                            ▼
                                  audited publish directory
```

### 7.2 禁止導入的 app graph

Site builder 與 site source 不得 import、copy 或 bundle：

- `frontend/src/app/App.tsx`
- `frontend/src/features/review/**`
- `frontend/src/lib/api/**`
- `app/**`
- `src/woundscope/review_api.py`
- `src/woundscope/model_runtime.py`
- `src/woundscope/gradio_app.py`
- Dockerfile 或 Hugging Face candidate files

可參考既有 WoundScope-authored design tokens、typography、spacing、abstract contour path 與 semantic hierarchy，但必須將所需的最小子集明確收旂在 static-site source boundary。不可以「不會執行那個 branch」為理由將 full review app 放進 bundle。

### 7.3 Zero-JavaScript contract

首版 publish directory 不得有 `.js`、`.mjs`、`.wasm` 或 source map。CSP 使用 `script-src 'none'`。Dark mode 以 `prefers-color-scheme` 實作，不使用 theme toggle、localStorage 或 inline script。

若未來需要 JavaScript，必須重新開啟 material design review；不可在一般 implementation 中擴大本 spec。

## 8. Evidence projection and SVG verification

### 8.1 Git-object verification order

Builder 必須按以下順序 fail closed：

1. `git cat-file -t` 確認 `1f51e659...` 是 `tag`。
2. 解析 tag object，確認名稱 `v0.2.2`、tagger identity `kuotunyu <61350295+kuotunyu@users.noreply.github.com>` 與 peeled commit `1b3df3b...`。
3. 確認 evidence commit 可讀，且 README、DATA_CARD、MODEL_CARD、SVG blob IDs 與第 2 節完全相符。
4. 從 evidence commit 的 README blob 只抽取唯一一組 `RESULTS_TABLE_START` 與 `RESULTS_TABLE_END` markers。
5. 解析表格 schema、row count、model IDs、loss、seeds 與 numeric fields；不接受 duplicate markers、額外 rows、NaN、欠欄或 locale-dependent parsing。
6. 從同一 structured result model 產生 HTML table 與 SVG consistency assertions。
7. 只在所有 checks 通過後才產生 publish directory。

Site template／CSS source 不得出現已知 metric literals。一個 source audit 必須拒絕 `0.8508`、`0.8270`、`0.7772`、`0.7437` 與 full result-table 數值在 generated evidence 以外出現，防止手抄漂移。

### 8.2 Aggregate SVG contract

`reports/public/model_comparison.svg` 必須從 evidence commit Git blob 以 `git cat-file blob` 讀出的 raw LF bytes 逐字節複製，不從 current worktree path 信任，也不得做任何 line-ending normalization、CRLF projection 或 XML reserialization。`3,059` bytes／`e2e8d211a33ac62942fac64eceae23def21a32c53b51039fe2c504421793b89c`／`model-comparison-e2e8d211a33ac629.svg` 只可作為 diagnostic-only 的 rejected noncanonical CRLF content 提及，永不得 export、validate 或用來導出 public filename。Builder 同時驗證：

- Git blob ID、byte length 與 SHA-256 與第 2 節相符。
- UTF-8 XML 可解析，且 root 只是 SVG。
- 必須有 `role="img"`、`aria-labelledby`、非空 `<title>` 與 `<desc>`。
- Element allowlist 只包含已審核的 `svg`、`title`、`desc`、`rect`、`text`、`g`、`line`。
- 拒絕 `DOCTYPE`、entity、script、style、foreignObject、image、use、iframe、event-handler attributes、`href`／`xlink:href`、`url(...)`、`data:` 與 remote font／asset references。
- SVG 的 model names、Dice／IoU 均值、`n=3 seeds`、official-validation 與 non-clinical caveat 必須與從 README 投影的 structured evidence 一致。

頁面以 same-origin `<img>` 使用這份 exact SVG，並提供不依賴圖形的：

- meaningful `alt`；
- figure caption；
- 在 SVG 之前的完整 semantic HTML results table；
- table caption 與 scope note，說明 200 張 Official Validation、3 seeds、image-level Bootstrap 與 non-clinical limitation。

## 9. Public artifact allowlist and denylist

### 9.1 Publish-directory exact allowlist

首版 publish directory 只能有：

```text
.nojekyll
index.html
404.html
LICENSE.txt
THIRD_PARTY_NOTICES.txt
sbom.spdx.json
pages-manifest.json
assets/site-<content-hash>.css
assets/model-comparison-<content-hash>.svg
```

`<content-hash>` 必須由檔案 bytes 產生，不可使用 timestamp、random value 或 machine path。任何額外檔案、directory、symlink、submodule、device file 或未知 binary 都使 build 失敗。

`pages-manifest.json` 的 per-file inventory **不得**記錄 `pages-manifest.json` 自身。它必須恰好列出下列八個 publish files，不多不少：

```text
.nojekyll
index.html
404.html
LICENSE.txt
THIRD_PARTY_NOTICES.txt
sbom.spdx.json
assets/site-<content-hash>.css
assets/model-comparison-<content-hash>.svg
```

Manifest 至少記錄：

- schema version、base path 與 build mode；
- site source commit；
- evidence tag object、peeled commit 與 source blob IDs；
- Node／Python 等實際使用之 build toolchain versions；
- 上述八個非 manifest 檔案的 POSIX path、bytes 與 lowercase SHA-256，其中包含 `sbom.spdx.json` 的 hash／bytes；
- 第 13 節定義的 tree digest；
- claim-boundary 與 network-contract version。

Manifest 不得包含自身的 hash 或 byte length。它的 SHA-256 只由 publish tree 外的 review receipt 記錄。

### 9.2 Denylist

Site content source、publish staging、publish directory，以及 CI review artifact 的 `publish/` payload 均必須拒絕下列內容。Pinned Playwright／axe 等 build-review tooling 可存在於獨立的 reviewer-tool source／dependency scope，但其 executable code、package cache 與 browser binaries 不得複製到 publish tree 或上傳的 review artifact：

- `.env`、`.env.*`、token、credential、private URL、machine-local absolute path。
- `data/**`、image-level manifest／result、patient／sample identifiers、CSV／Parquet／JSONL 等 tabular artifacts。
- `artifacts/**`、`reports/generated/**`、`reports/error_gallery/**`、`reports/sample_predictions/**`。
- checkpoint、weight、ONNX、calibration、Torch／NumPy model artifact suffixes。
- Raster image suffixes，包含過時的 `woundscope-ui-showcase.webp`。
- 任何 wound-like synthetic sample，即使不是真實醫療資料。
- API route、`fetch`、XMLHttpRequest、WebSocket、EventSource、sendBeacon、FormData、file input、service worker 或 model-download code。
- JavaScript、WebAssembly、source maps、debug logs、test snapshots、cache、coverage 與 browser traces。
- Remote CSS import、font、image、script、iframe、video、audio 或 tracking pixel。
- `AGENTS.md`、`.agents/**`、`PROJECT_PLAN.md`、`PROGRESS.md`、interview、permission draft 或其他 local control artifacts。
- Docker、FastAPI、Gradio、HF candidate 或任何 server runtime files。

## 10. External navigation allowlist

外部 navigation 只允許使用者主動點擊。所有外部 `<a>` 必須使用 `target="_blank" rel="noopener noreferrer"`，且 normalized URL 必須等於下列 allowlist 之一：

- `https://github.com/kuotunyu/WoundScope`
- `https://github.com/kuotunyu/WoundScope/releases/tag/v0.2.2`
- `https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/README.md`
- `https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/DATA_CARD.md`
- `https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/MODEL_CARD.md`
- `https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/CITATION.cff`
- `https://github.com/kuotunyu/WoundScope/blob/1b3df3b516cc4d366dc9da3cb01e8d0a319be613/LICENSE`
- `https://doi.org/10.1038/s41598-020-78799-w`
- `https://github.com/uwm-bigdata/wound-segmentation/tree/42a272dfe0679f20675e826385925cb7562934b6/data/Foot%20Ulcer%20Segmentation%20Challenge`

不允許 link shortener、redirector、branch-floating evidence link、query-based tracking parameter、`javascript:`、`data:`、`mailto:` 或 user-provided URL。首版不連到 Hugging Face、model artifact 或 live inference service。

Builder 與 browser gate 不得 prefetch、preconnect、prerender 或自動檢索這些外部 URLs。

## 11. Privacy, security and CSP

### 11.1 No-external-runtime-request contract

頁面初始載入、捲動、改變 viewport、切換 OS color scheme、focus 與 keyboard navigation 期間，唯一允許的 requests 是 current origin 下 `/WoundScope/` 的 allowlisted publish files。

Playwright 必須在 page context 建立前監聽 requests；任何不是 same-origin `/WoundScope/**` 的 request 立即使 gate 失敗。External link 只做 DOM attribute 與 allowlist 驗證，自動化測試不點擊到網路。

### 11.2 Content Security Policy

`index.html` 與 `404.html` 必須包含與 zero-JavaScript 邊界一致的 meta CSP：

```text
default-src 'none';
style-src 'self';
img-src 'self';
font-src 'none';
script-src 'none';
connect-src 'none';
media-src 'none';
object-src 'none';
frame-src 'none';
base-uri 'none';
form-action 'none';
manifest-src 'none'
```

Meta CSP 是 GitHub Pages 無自訂 response headers 時的 defense-in-depth，不得把它誤述為 response-header 保證。必須另以 artifact audit 與 browser request interception 驗證邊界。

### 11.3 Additional controls

- 沒有 form、input、contenteditable、download attribute 或 clipboard API。
- 所有顯示內容在 render 前做 HTML escaping；evidence parser 不把 Markdown 當 HTML 直接注入。
- 404 頁面不回顯 request path 或 query string。
- Publish artifact 不含 Git metadata、environment dump、absolute path、username、runner path 或 build log。
- Actions 的第三方 steps 必須以 40-character immutable commit SHA pin。
- Review workflow 不使用 secrets，不使用 `pull_request_target`，不從 untrusted PR 執行 privileged deployment。

## 12. License, SBOM and NOTICE

首版雖然預期沒有 runtime JavaScript dependency，仍必須完成機器可驗證的 distribution license gate。

### 12.1 Required outputs

- `LICENSE.txt`：從 site source commit 的 WoundScope Apache-2.0 `LICENSE` 逐字節投影。Normative identity contract 固定為 `<site_source_sha>:LICENSE` 必須解析到 Git blob `6d7d4eed049964731c06b000d257a1bdb2fd6028`，其 raw size 必須是 `11,577` bytes，raw SHA-256 必須是 `7203278db33515a51443fb4969f84deabc6081086c55a59cc94ee2a384c83f7d`。Byte domain 僅限對該已選定 Git object 執行 `git cat-file blob` 讀出的 raw bytes，直接複製到 `LICENSE.txt`；不得讀取 checkout／worktree `LICENSE`、不得做 line-ending normalization、CRLF projection 或 reserialization。`11,782` bytes／`46f4aa5b30f1e3fdec3c30ff381da83fe0323a00d8d7bde8f1a16265c1305fd1` 只可作為 diagnostic-only 的 rejected noncanonical working-copy variant 提及，永不得 export、validate 或作為 hash／budget assertion 來源。
- `THIRD_PARTY_NOTICES.txt`：列出每個實際 bundled production component 的 name、version／source revision、license identifier、copyright，以及必要 license text／attribution。
- `sbom.spdx.json`：符合 SPDX JSON schema，記錄實際 bundled production components，並為 publish tree 中除 `sbom.spdx.json` 與 `pages-manifest.json` 以外的七個檔案建立可驗證 file records；SBOM 不記錄自身 checksum。
- CI review artifact 另保存 build-tool dependency report；build-only tools 不可被誤列為網頁 runtime code。

### 12.2 Acyclic cross-file contract

完整性資料必須形成單向、無循環的 DAG：

1. `sbom.spdx.json` 記錄七個非 SBOM、非 manifest publish files 的 checksum／license relationship，以及 bundled production components；不記錄自身或 manifest。
2. `pages-manifest.json` 記錄全部八個非 manifest publish files，因而包含 SBOM 的 SHA-256／bytes，並記錄以同一八檔集合計算的 publish tree digest；不記錄自身。
3. Publish tree 外的 `review-receipt.json` 記錄 manifest SHA-256、SBOM SHA-256、publish tree digest、site source SHA 與 evidence tag object／peeled SHA。

Gate 依這個順序重算並逐欄比較，任何缺檔、多檔、checksum／bytes／relationship 不符都 fail closed。不得以「SBOM 與整棵 publish tree 相互雜湊一致」等會要求 self-reference 的條件取代此 contract。

### 12.3 License gate

- 對 publish directory 內每個 nontrivial authored／third-party file 建立 source 與 license record。
- 如 production dependency set 為空，NOTICE 必須明確說明沒有 bundled third-party runtime package；不得省略檔案。
- Unknown、missing、custom、non-commercial-only、copyleft 或 incompatible license 都必須 fail，由 owner 另行審閱；實作者不可自行添加例外。
- System fonts 只以 CSS fallback names 參考，不得把 font bytes 打包進 site。
- FUSeg attribution 與 data-use ambiguity 在頁面與 SBOM／NOTICE 中不得被 Apache-2.0 覆蓋。Aggregate facts／chart 的來源必須指向 pinned dataset revision 與原論文。

## 13. Deterministic build and tree digest

Build 必須在兩個全新 OS temporary directories 各執行一次，並產生 byte-identical allowlisted files。

可重現性規則：

- Locale、timezone、filesystem enumeration order 與 text line-ending policy 不可影響 bytes；aggregate SVG 的 canonical byte domain 一律是 `git cat-file blob` 回傳的 raw LF bytes，而非 worktree 或 CRLF projection。
- `SOURCE_DATE_EPOCH` 從 site source commit time 取得，不使用 wall-clock time。
- JSON keys 排序、UTF-8 without BOM、LF line endings、固定 indentation；但 approved aggregate SVG 不重寫，直接保留其 raw blob bytes。
- CSS filename 與 SVG filename 只使用 content hash。
- 無 random IDs、UUID、absolute path、runner name 或 nondeterministic minifier banner。

Tree digest algorithm 固定為：

1. 排除 `pages-manifest.json`，避免 self-reference；輸入必須恰好是第 9.1 節列出的其餘八個 regular files。
2. 對這八個 files 計算 SHA-256 與 byte length。
3. 將 POSIX relative paths 以 UTF-8 byte order 排序。
4. 每筆 record 編碼為 `path NUL bytes NUL lowercase_sha256 LF`。
5. 對連接後的 records 再做 SHA-256，得到 `publish_tree_sha256`。

Manifest 記錄 tree digest，但不在內部記錄自己的 digest／bytes。Publish tree 外的 `review-receipt.json` 必須記錄 manifest SHA-256、SBOM SHA-256 與 tree digest，讓 reviewer 從 receipt 單向驗證 manifest，再由 manifest 驗證其餘八檔。

瀏覽器不執行 runtime digest verification。Zero-JavaScript 完整性是 build、CI review 與未來 deployment tree 的 gate；production HTML 不得宣稱已在 client side 做 cryptographic verification，也不得為此加入 JavaScript、WebAssembly 或 remote runtime。

## 14. Accessibility, responsive and browser gates

### 14.1 Semantic and accessibility contract

- `<html lang="zh-Hant-TW">`、unique title、description、canonical candidate URL 與 viewport metadata。
- 一個 H1；heading levels 不跳級；header、nav、main、section、figure、table、footer 使用正確 semantics。
- 第一個 focusable element 是 skip link，並能將 focus 移到 main content。
- 只有連結可 focus；沒有偽 button、tab 或不可用 controls。
- Visible focus、keyboard-only order、連結文字目的清楚、不只用顏色表達狀態。
- Normal text contrast 至少 4.5:1，large text／focus／non-text contrast 至少 3:1；light 與 dark 分開驗證。
- 200% browser zoom 時不遺失內容、不重疊、不產生 two-dimensional scrolling。
- `prefers-reduced-motion` 下無非必要 animation。首版原則上不需要 animation。
- Aggregate SVG 不是 table 的唯一表達；關閉 images 或 high-contrast mode 仍可取得完整 evidence。

### 14.2 Viewport matrix

至少在 light／dark 中驗證：

- 375×667
- 390×844
- 768×1024
- 1024×768
- 1440×900

每個 viewport 必須檢查 horizontal overflow、clipped text、table readability、footer visibility、focus outline 與至少 44×44 px 的 touch target（如適用）。Narrow viewport 的 results table 可在明確標記的 table container 內水平捲動，但 page body 不得水平捲動，且要有不依賴 hover 的提示。

### 14.3 Browser and reviewer toolchain matrix

Implementation plan 必須鎖定 exact `@playwright/test`、`axe-core` 與相關 reviewer-tool versions，不接受 `latest`、`current`、caret／tilde range 或未鎖定 transitive dependency。Chromium、Firefox、WebKit 必須以可驗證的 Playwright browser revisions 執行；或者整組 reviewer toolchain 使用 digest-pinned image，並在 review receipt 記錄 exact package versions、browser revisions／image digest 與 lockfile digest。

三引擎都必須通過 DOM、request、console、keyboard、axe 與 screenshot review gates。Axe 可由 pinned local test tooling 注入 page context，但不可發出 network request，也不可把 script、source map 或 dependency bytes 寫入 production publish directory；production artifact 仍須為 0 JavaScript。視覺 snapshots 只使用頁面自身的 abstract SVG／aggregate evidence，不準備醫療或 wound-like fixtures。

## 15. GitHub Pages subpath and 404 contract

- Production base path 固定為 `/WoundScope/`，大小寫不可變。
- 所有 internal assets 使用 `/WoundScope/...` 或相對 URL，不得指向 root `/assets/...`。
- 頁內 navigation 使用 anchors，不需要 SPA fallback。
- `404.html` 是獨立、無 JavaScript、無 path echo 的小型頁面，只說明找不到頁面並連回 `/WoundScope/`。
- Test server 必須以 Pages-like subpath 提供 artifact，而不是只在 `/` 測試。
- Gates 至少覆蓋 `/WoundScope/`、CSS、SVG、NOTICE、SBOM、manifest、unknown path 與 direct reload。
- 在 activation 前，candidate URL 繼續 404 是預期狀態，不能藉此略過 local／CI subpath gate。

## 16. CI review artifact and later activation gate

### 16.1 Review workflow

Implementation 階段先新增只負責 build／test／review artifact 的 workflow。它必須：

- 在 pull request、push 與 manual dispatch 執行。
- 使用 full history，以驗證 annotated tag 與 evidence Git objects。
- Top-level permissions 只有 `contents: read`。
- 不包含 `pages: write`、`id-token: write`、environment deployment 或 GitHub Pages configuration calls。
- 執行 evidence projection、double-build reproducibility、bundle audit、license／SBOM／NOTICE、accessibility、browser、subpath 與 privacy gates。
- 上傳短期 CI review artifact，其結構明確分離：`publish/` 只能是第 9.1 節 exact site tree；tree 外的 `review-receipt.json` 記錄 manifest／SBOM／tree digests 與 dual provenance；`reports/` 才保存 screenshots、request log、axe report、toolchain／browser revisions、dependency-license report 與 gate summary。
- Review artifact 不得包含 source maps、browser profile、cookies、environment dump、absolute path 或未在本節 artifact 結構允許的 files；`publish/` 的 allowlist 與 `review-receipt.json`／`reports/` 的 review-only allowlist 不可混為一談。

### 16.2 Activation workflow

Pages activation、deploy workflow 與 About Website 設定是下一個獨立中央 gate。當且僅當 review artifact 與 exact commit 被人工核准後，才可設計／啟用：

- build job `contents: read`；
- deploy job 最小 `pages: write` 與 `id-token: write`；
- `github-pages` environment 與人工核准／branch protection；
- exact reviewed artifact digest 與 site source SHA binding；
- deploy 後的 URL、CSP、request、accessibility 與 rollback smoke。

本 spec commit 不新增 activation workflow、不改 repository Pages settings，不設定 About URL。

## 17. Failure states

以下任一情況必須使 build／review gate 失敗，且不產生可 deploy artifact：

- Remote `main` 或指定 implementation base 與已批准 SHA 不同。
- `v0.2.2` 不是預期 annotated tag object，或 peeled commit／blob 不同。
- Evidence marker、schema、row count、model ID、seed 或 numeric parse 失敗。
- SVG bytes、SHA、XML allowlist、accessible metadata 或 metrics 不同。
- Metric literal 出現在 generated evidence 以外的 site source。
- Publish directory 有未列名 file、symlink、raster、JavaScript、source map、secret-like content、absolute path 或 private artifact。
- Browser 觀察到 external request、console error、CSP violation 或 unexpected same-origin request。
- External link 不在 allowlist，或缺 `noopener noreferrer`。
- License missing／unknown／incompatible，NOTICE 不完整，或第 12.2 節的 SBOM → manifest → receipt 單向完整性 contract 不一致。
- Axe、keyboard、contrast、zoom、viewport、browser 或 subpath／404 gate 失敗。
- 兩次 clean build 的 file inventory、bytes 或 tree digest 不同。
- Workflow 需要 secret、privileged event 或 Pages deployment permission。
- Implementation Task 0 未能同步 `AGENTS.md`、`PROJECT_PLAN.md`、`PROGRESS.md` 的 path／release／site decision，或同步結果被錯誤納入 public site／CI artifact／app-source scope。

錯誤輸出只提供固定 error code、規則與 public relative path，不回顯檔案內容、credential、absolute path 或 environment values。

## 18. Acceptance criteria

實作只有在下列條件全數有 fresh evidence 時才可進入 Pages activation review：

1. Governance：implementation Task 0 已先同步 ignored／private `AGENTS.md`、`PROJECT_PLAN.md`、`PROGRESS.md`，且無 stale path／release／site decision；三者未進入 public site、CI artifact 或 app-source commit。
2. Base：implementation branch 可追溯至已批准 remote base `b6f2303...`，沒有未解釋的 upstream drift。
3. Provenance：site source SHA 與 evidence release／peeled SHA 在 UI 與 manifest 中分開顯示。
4. Evidence：metrics 只從 evidence README Git blob 投影，source 中無手抄 metric literals。
5. SVG：exact blob、3,009 bytes、SHA-256、raw `git cat-file blob` LF bytes、XML allowlist、title／desc 與 metrics consistency 全數 PASS。
6. Claims：zh-TW-first，research-only，non-clinical，且所有禁止 claims 為 0。
7. Boundary：publish artifact 只有第 9.1 節的 files，含 0 raster、0 JavaScript、0 API／upload／inference code、0 private artifact。
8. Network：三瀏覽器完整操作期間只產生 same-origin `/WoundScope/**` requests。
9. CSP：HTML 包含 exact zero-JavaScript CSP，無 inline style／script 或 remote asset。
10. Links：所有 external links 均在 exact allowlist 且有 `target="_blank" rel="noopener noreferrer"`。
11. License：Apache-2.0 project license、NOTICE、SPDX SBOM、無循環 SBOM → manifest → receipt contract 與 dependency license review PASS；unknown／incompatible licenses為 0。
12. Accessibility：axe serious／critical violations 為 0，heading／table／link／keyboard／focus／contrast／zoom 全數 PASS。
13. Responsive：指定五種 viewports 在 light／dark 均無 body horizontal overflow、clipping 或 hidden footer。
14. Browser：以 exact locked reviewer tools 與可驗證 browser revisions／image digest 執行的 Chromium、Firefox、WebKit，均無 console error、unexpected request 或 material visual regression；axe 注入未進入 production artifact。
15. Subpath：`/WoundScope/`、assets、direct reload、NOTICE／SBOM／manifest 與 safe 404 全數 PASS。
16. Determinism：兩次 clean build byte-identical，非 manifest 八檔的 publish tree digest 一致；receipt 可重算 manifest／SBOM／tree digests，瀏覽器與頁面不宣稱 runtime cryptographic verification。
17. Privacy：repository-index audit、publish-bundle audit、secret／absolute-path scan 全數 PASS。
18. CI：review workflow 只有 read permissions，產生可審閱 artifact，並未 deploy。
19. Identity：implementation commits 的 author／committer 只有 `kuotunyu <61350295+kuotunyu@users.noreply.github.com>`，沒有 co-author trailer。
20. Activation：另一個中央核准已審閱 exact artifact digest、Pages permissions、About URL 與 rollback；沒有該核准就維持未部署。

## 19. Spec review and implementation handoff

本 spec 不包含 placeholder，也不授權 implementation。中央 review 必須先確認下列設計點：

- 首版採 zero-runtime-JavaScript，不打包 React／Lucide／API app。
- Evidence 來自 `v0.2.2` Git objects，site source 與 evidence provenance 永久分離。
- Publish allowlist 包含 public SPDX SBOM 與 THIRD_PARTY_NOTICES。
- Review workflow 與 Pages activation workflow 分離；首次 implementation 不啟用 Pages。
- 過時 WebP、sample prediction、medical／wound-like raster 全數排除。

核准本 spec 後，下一步是使用 `writing-plans` 撰寫 implementation plan。該 plan 的 Task 0 必須完成第 3 節的 local governance sync；執行 implementation 時不可跳過 Task 0 直接進入 site code 或 workflow。
