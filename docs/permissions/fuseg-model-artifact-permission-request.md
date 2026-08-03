# FUSeg model artifact 授權詢問草稿（尚未發送）

> 此草稿尚未發送。收件人應由專案維護者依官方來源確認為 FUSeg dataset maintainer 或 rights holder；本文件不假設姓名、email、授權版本或 legal code。

收件者：FUSeg dataset maintainer / rights holder（待依官方來源確認）

主旨：請確認 FUSeg 衍生模型與公開推論的授權範圍

您好：

我們正在維護 WoundScope，這是使用 FUSeg 做研究用途 wound segmentation 的開放原始碼專案。WoundScope 自有程式碼採 Apache-2.0；我們不會將該授權延伸解讀為 FUSeg 資料或衍生 model artifacts 的權利。Challenge 文件中出現「CC BY-NC」，但我們未找到可確認的版本、正式 legal code 或 repository LICENSE，因此希望在任何外部發佈前取得您的明確指示。

目前我們沒有建立 Hugging Face Space 或 model repository、沒有上傳資料／權重／ONNX、沒有使用 token，也沒有啟用公開服務。若您是適當的聯絡窗口，煩請協助確認下列問題；若不是，也請指示正確的 FUSeg dataset maintainer 或 rights holder。

1. 「CC BY-NC」適用的確切 license version 與 legal code／授權連結為何？是否還有其他資料使用、保留或散布限制？
2. 是否允許以 FUSeg 訓練或微調後的 derived model weights 儲存在 private storage？可否指定可存取者、保留期限或必要條件？
3. 是否允許將 derived model weights 用於 public non-commercial inference？若可以，是否只限於特定平台、地區、使用者或用途？
4. 是否允許散布 checkpoint、ONNX 或其他可供推論的 model artifact？若可以，應採 Public、Protected 或 Private 何種可見性？
5. 需要如何呈現 attribution（資料集、論文、作者、license notice 或其他文字）？是否需要在 UI、repository、model card 或輸出中保留特定聲明？是否禁止上傳原始 images、labels、含原圖的結果、image-level manifest 或其他衍生內容，並對暫存、刪除與 audit record 有何要求？

在收到明確書面許可前，我們會維持 `PERMISSION_PENDING`，僅保留 code-only candidate，且不會對外建立或上傳任何模型相關資產。若獲允許，我們也會保留非臨床用途與人工複核說明，不將結果作為診斷、嚴重度、預後或治療建議。

謝謝您的協助。
