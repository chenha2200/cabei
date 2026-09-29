# CABEI 機構採購｜台灣商機雷達

這個版本採用不需外部部署 Token 的自動更新流程：

```text
CABEI 公開資料介面
        ↓
GitHub Actions（每日 08:00，台灣時間）
        ↓
public/data/opportunities.json
        ↓
GitHub 自動提交
        ↓
Cloudflare Pages Git 整合自動部署
```

## 自動更新內容

- 取得 CABEI「進行中機構採購」清單。
- 僅保留截止時間仍在未來的案件。
- 同步案號、原文標題、公告日、截止日、採購方式、類別及官方附件。
- 保留已人工整理的繁體中文摘要、資格、金額與台灣廠商建議。
- 新案件以關鍵字規則產生產業、能力、適配分數及基本中文說明；完整資格及 TOR 摘要仍應人工覆核。
- 只有資料異動時才提交，因此 Cloudflare Pages 不會做無意義的重複部署。

## GitHub Actions

工作流程位於 `.github/workflows/update-cabei.yml`，每天台灣時間 08:00 執行，也可在 GitHub 的 **Actions → Update CABEI opportunities → Run workflow** 手動執行。

流程只使用 GitHub 內建的 `GITHUB_TOKEN` 提交同一個儲存庫，不需要建立 CABEI、OpenAI 或 Cloudflare API Token。

## Cloudflare Pages 設定

1. 登入 Cloudflare Dashboard。
2. 進入 **Workers & Pages → Create application → Pages → Connect to Git**。
3. 連接 GitHub 並選擇本儲存庫。
4. Production branch 設為 `main`。
5. Framework preset 選 `None`。
6. Build command 留空。
7. Build output directory 填入 `public`。
8. 按 **Save and Deploy**。

完成一次連接後，每當 GitHub Actions 更新 JSON 並推送，Cloudflare Pages 就會自動部署。

## 本機測試

```bash
npm run check
npm run update
npx serve public
```

## 資料來源

- https://www.bcie.org/adquisiciones-institucionales/en-curso

