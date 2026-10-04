"""Email CABEI update status via the user's SMTP account; stdlib only."""
import json
import os
import smtplib
import ssl
import time
import urllib.request
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def api(path):
    request = urllib.request.Request(
        "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + path,
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                 "Accept": "application/vnd.github+json", "User-Agent": "CABEI-status"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

def deployment_status(sha, attempts=12):
    for index in range(attempts):
        checks = api("/commits/" + sha + "/check-runs").get("check_runs", [])
        checks = [x for x in checks if x.get("name") == "Cloudflare Pages"
                  and x.get("app", {}).get("slug") == "cloudflare-workers-and-pages"]
        if checks:
            check = max(checks, key=lambda x: x["id"])
            if check["status"] == "completed":
                return "success" if check.get("conclusion") == "success" else "failure"
        if index + 1 < attempts:
            time.sleep(15)
    return "pending"

def compose(update_result, deployment, snapshot_label="本次資料"):
    run_url = os.environ["GITHUB_SERVER_URL"] + "/" + os.environ["GITHUB_REPOSITORY"] + "/actions/runs/" + os.environ["GITHUB_RUN_ID"]
    if update_result != "success":
        status = "更新失敗／未完成"
    elif deployment == "success":
        status = "更新與部署成功"
    elif deployment == "failure":
        status = "資料更新成功，Cloudflare 部署失敗"
    else:
        status = "資料更新成功，部署尚未確認"
    lines = [status, "", "執行紀錄：" + run_url,
             "機構採購：https://cabei.pages.dev/",
             "專案採購：https://cabei.pages.dev/projects/", ""]
    for name, path in [("機構採購", "public/data/opportunities.json"),
                       ("專案採購", "public/projects/data/opportunities.json")]:
        try:
            data = json.loads((ROOT / path).read_text(encoding="utf-8"))
            items = data.get("opportunities", [])
            review = sum(bool(x.get("translationWarnings")) for x in items)
            lines.append(f"{name}（{snapshot_label}）：{len(items)} 筆；待校訂 {review} 筆。")
        except (OSError, ValueError):
            lines.append(name + "：無法讀取本次資料統計。")
    lines.extend(["", "翻譯為機器翻譯及術語校正；請以官方公告及附件為準。"])
    if update_result != "success":
        try:
            jobs = api("/actions/runs/" + os.environ["GITHUB_RUN_ID"] + "/jobs").get("jobs", [])
            for job in jobs:
                for step in job.get("steps", []):
                    if step.get("conclusion") == "failure":
                        lines.append("失敗步驟：" + step["name"])
        except Exception:
            lines.append("失敗步驟請查看上方執行紀錄。")
    return "[CABEI] " + status, "\n".join(lines)

def send(subject, body):
    sender = os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]
    recipient = os.environ["MAIL_TO"]
    for address in (sender, recipient):
        if "\n" in address or "\r" in address or parseaddr(address)[1] != address or "@" not in address:
            raise ValueError("Use a single plain email address")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, recipient, subject
    message.set_content(body)
    host = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT") or "465")
    context = ssl.create_default_context()
    if port == 465:
        client = smtplib.SMTP_SSL(host, port, timeout=30, context=context)
    elif port == 587:
        client = smtplib.SMTP(host, port, timeout=30)
        client.ehlo()
        client.starttls(context=context)
        client.ehlo()
    else:
        raise ValueError("SMTP_PORT must be 465 or 587 with TLS")
    with client:
        client.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        client.send_message(message)

def main():
    required = ("SMTP_USER", "SMTP_PASSWORD", "MAIL_TO")
    if any(not os.environ.get(key) for key in required):
        print("::warning::Email 未啟用：請設定 SMTP_USER、SMTP_PASSWORD、MAIL_TO Secrets。")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as output:
                output.write("### Email 未啟用\n請依 EMAIL-NOTIFICATIONS.md 設定寄信 Secrets。\n")
        return
    result = os.environ.get("UPDATE_RESULT", "failure")
    deployment = "pending"
    if result == "success":
        try:
            deployment = deployment_status(os.environ["DATA_SHA"])
        except Exception:
            # An API timeout is never reported as deployment success.
            deployment = "pending"
    subject, body = compose(result, deployment, "本次資料" if result == "success" else "既有資料快照")
    try:
        send(subject, body)
    except Exception as error:
        # Do not log SMTP responses or credentials.
        print("::error::Email 寄送失敗（" + type(error).__name__ + "）；請確認寄信授權與設定。")
        raise SystemExit(1)
    print("Email 已交由 SMTP 伺服器接受；實際到信仍取決於收件伺服器。")

if __name__ == "__main__":
    main()

