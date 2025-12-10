# notification/channels/wework.py
import requests
import time
import re
from typing import Dict, Optional
from ...config import CONFIG
from ...utils.text import strip_markdown
from ...reporting import split_content_into_batches, add_batch_headers, get_max_batch_header_size


def send_to_wework(
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
    log_prefix = f"企业微信{account_label}" if account_label else "企业微信"

    msg_type = CONFIG.get("WEWORK_MSG_TYPE", "markdown").lower()
    is_text_mode = (msg_type == "text")
    format_type = "wework_text" if is_text_mode else "wework"

    wework_batch_size = CONFIG.get("MESSAGE_BATCH_SIZE", 4000)
    header_reserve = get_max_batch_header_size(format_type)
    batches = split_content_into_batches(
        report_data, "wework", update_info, max_bytes=wework_batch_size - header_reserve, mode=mode
    )
    batches = add_batch_headers(batches, format_type, wework_batch_size)

    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")
    for i, content in enumerate(batches, 1):
        if is_text_mode:
            text = strip_markdown(content)
            payload = {"msgtype": "text", "text": {"content": text}}
        else:
            payload = {"msgtype": "markdown", "markdown": {"content": content}}

        try:
            resp = requests.post(webhook_url, json=payload, headers=headers, proxies=proxies, timeout=30)
            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功")
                if i < len(batches):
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
            else:
                print(f"{log_prefix}第 {i} 批次失败: {resp.json().get('errmsg')}")
                return False
        except Exception as e:
            print(f"{log_prefix}发送出错: {e}")
            return False
    return True