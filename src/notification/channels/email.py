# notification/channels/email.py
import smtplib
import traceback
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from ...config import SMTP_CONFIGS
from ...utils.time import get_beijing_time


def send_to_email(
    from_email: str,
    password: str,
    to_email: str,
    report_type: str,
    html_file_path: str,
    custom_smtp_server: str = "",
    custom_smtp_port: str = "",
) -> bool:
    try:
        if not html_file_path or not Path(html_file_path).exists():
            print(f"错误：HTML文件不存在: {html_file_path}")
            return False
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        domain = from_email.split("@")[-1].lower()
        if custom_smtp_server and custom_smtp_port:
            smtp_server = custom_smtp_server
            smtp_port = int(custom_smtp_port)
            use_tls = (smtp_port == 587)
        elif domain in SMTP_CONFIGS:
            cfg = SMTP_CONFIGS[domain]
            smtp_server = cfg["server"]
            smtp_port = cfg["port"]
            use_tls = (cfg["encryption"] == "TLS")
        else:
            smtp_server = f"smtp.{domain}"
            smtp_port = 587
            use_tls = True

        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("TrendRadar", from_email))
        msg["To"] = ", ".join(addr.strip() for addr in to_email.split(","))
        now = get_beijing_time()
        subject = f"TrendRadar 热点分析报告 - {report_type} - {now.strftime('%m月%d日 %H:%M')}"
        msg["Subject"] = Header(subject, "utf-8")
        msg["MIME-Version"] = "1.0"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        text_part = MIMEText(f"TrendRadar报告\n类型：{report_type}\n时间：{now}", "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(text_part)
        msg.attach(html_part)

        print(f"正在发送邮件到 {to_email}...")
        if use_tls:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()
        print(f"邮件发送成功 [{report_type}] -> {to_email}")
        return True
    except Exception as e:
        print(f"邮件发送失败 [{report_type}]：{e}")
        traceback.print_exc()
        return False