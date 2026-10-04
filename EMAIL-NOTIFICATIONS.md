# GitHub Actions Email 通知

程式已備妥，但沒有寄信授權時不會寄信。GitHub Secrets 不要貼進聊天或提交到程式碼。

在 repository 的 Settings → Secrets and variables → Actions 建立：

| Repository Secret | 內容 |
|---|---|
| SMTP_USER | 寄件信箱 |
| SMTP_PASSWORD | 信箱提供者的 SMTP／應用程式密碼 |
| MAIL_TO | 接收通知的單一 Email 地址 |
| MAIL_FROM | 可省略，預設 SMTP_USER |

預設 Gmail：smtp.gmail.com、SSL 465。使用其他 SMTP 時，在同頁 Variables 設 SMTP_HOST、SMTP_PORT；支援 465 SSL 或 587 STARTTLS。

Gmail 應用程式密碼入口：https://myaccount.google.com/apppasswords
Google 說明：https://support.google.com/accounts/answer/185833
必須先開啟兩步驟驗證；若帳號政策不允許應用程式密碼，使用允許 SMTP 的其他寄件服務。

設好後到 Actions → Update CABEI opportunities → Run workflow，確認 Email update result 工作成功，並實際查看收件匣／垃圾郵件。

通知包含兩站網址、案件與待校訂筆數、執行紀錄。只有 Cloudflare 對本次資料 commit 的 check 成功才稱部署成功；逾時則通知「部署尚未確認」。寄信失敗會在工作紀錄明示，SMTP 接受郵件不等於收件匣一定到信。

此流程不使用 ChatGPT。SMTP 密碼失效、信箱限制或 GitHub／Cloudflare 服務故障仍可能影響執行。
