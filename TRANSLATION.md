# 專案採購離線翻譯

專案版使用免費的 Hugging Face Transformers、Helsinki-NLP OPUS-MT 西班牙文→英文→中文模型，再用 OpenCC 轉成台灣繁體中文。模型權重以 commit 固定版本，不呼叫翻譯 API，也不需要金鑰。

- https://huggingface.co/Helsinki-NLP/opus-mt-es-en
- https://huggingface.co/Helsinki-NLP/opus-mt-en-zh

上述模型標示 Apache-2.0 授權。模型與依賴由 GitHub Actions 快取；只重新翻譯有異動的來源。OPUS-MT checkpoint 的繁體分支在實測中漏譯子句，改採簡體分支加 OpenCC；這是本案測試結果，不代表所有文本通用排名。

真實公告測試包含殺蟲劑／殺菌劑、SIEPAC 工程外部監督、飲用水系統，以及金額、數量及 Email 地址保留。這些測試確認基本內容存在，不等於完整語意已經人工審校。

翻譯前不丟棄長公告範疇。重要數字、Email、URL、縮寫受保護；分段重試會標示待校訂。原始中文標題修訂依原文與案號綁定，官方修改原文後不自動套用舊修訂。

機構版維持既有翻譯引擎及校訂內容，不切換為 OPUS-MT。

文件取得入口、Email 索取或需要登入的附件，不聲稱已讀完整文件。無法擷取時顯示實際限制。日期及金額仍使用官方結構化欄位。

部署前會跑 scripts/test-opus-quality.py；下載、翻譯或測試失敗則不提交新的 JSON，保留公開網站上一份資料。每日排程不依赖 ChatGPT，但 GitHub、模型下載來源及 CABEI 可能暫時無法連線，因此不能保證永不失敗。
