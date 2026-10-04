# CABEI 專案採購版

公開網址：https://cabei.pages.dev/projects/

與機構採購版共用 Cloudflare Pages 的 Git 整合，使用獨立資料、追蹤儲存與藍紫色樣式。

每日 GitHub Actions 排程為 UTC 00:00（台灣 08:00）；GitHub 可能延遲執行。可手動執行 Update CABEI opportunities。

更新順序：取得機構公告 → 取得專案公告（完整分頁）→ 離線中文翻譯與 PDF 擷取 → 提交兩份 JSON → Cloudflare 自動部署。

無須 OpenAI 或 Cloudflare API token。提交僅使用 GitHub Actions 內建 GITHUB_TOKEN；Cloudflare 必須保留既有 GitHub 連線。

未明示 USD 的 API 金額不轉成美元。個人顧問不列企業投標候選；企業建議是技術適配研判，不是資格認證。無法擷取 PDF 時顯示公告摘要，明示並非文件內容摘要。翻譯由本機模型處理，仍須核對官方原文。

本機驗證：

```sh
node scripts/update-projects.mjs
node scripts/test-projects.mjs
python scripts/translate-projects.py
```

Cloudflare 建置輸出資料夾維持 public，不必改動部署設定。原 Sites 網址不會隨這套流程同步。
