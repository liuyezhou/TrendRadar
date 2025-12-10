# notification/channels/slack.py
import requests
import time
import re
from typing import Dict, Optional
from ...config import CONFIG
from ...reporting import split_content_into_batches, add_batch_headers, get_max_batch_header_size


def convert_markdown_to_mrkdwn(content: str) -> str:
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', content)
    content = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', content)
    return content


def send_to_slack(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
) -> bool:
    headers = {"Content-Type": "application/json"}
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    log_prefix = f"Slack{account_label}" if account_label else "Slack"

    slack_batch_size = CONFIG["SLACK_BATCH_SIZE"]
    header_reserve = get_max_batch_header_size("slack")
    batches = split_content_into_batches(
        report_data, "slack", update_info, max_bytes=slack_batch_size - header_reserve, mode=mode
    )
    batches = add_batch_headers(batches, "slack", slack_batch_size)

    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")
    for i, content in enumerate(batches, 1):
        mrkdwn = convert_markdown_to_mrkdwn(content)
        payload = {"text": mrkdwn}
        try:
            resp = requests.post(webhook_url, json=payload, headers=headers, proxies=proxies, timeout=30)
            if resp.status_code == 200 and resp.text.strip() == "ok":
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功")
                if i < len(batches):
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
            else:
                print(f"{log_prefix}第 {i} 批次失败: {resp.text}")
                return False
        except Exception as e:
            print(f"{log_prefix}发送出错: {e}")
            return False
    return True