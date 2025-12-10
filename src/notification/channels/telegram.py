# notification/channels/telegram.py
import requests
import time
from typing import Dict, Optional
from ...config import CONFIG
from ...reporting import split_content_into_batches, add_batch_headers, get_max_batch_header_size


def send_to_telegram(
    bot_token: str,
    chat_id: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    headers = {"Content-Type": "application/json"}
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    log_prefix = f"Telegram{account_label}" if account_label else "Telegram"

    telegram_batch_size = CONFIG.get("MESSAGE_BATCH_SIZE", 4000)
    header_reserve = get_max_batch_header_size("telegram")
    batches = split_content_into_batches(
        report_data, "telegram", update_info, max_bytes=telegram_batch_size - header_reserve, mode=mode
    )
    batches = add_batch_headers(batches, "telegram", telegram_batch_size)

    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")
    for i, content in enumerate(batches, 1):
        payload = {
            "chat_id": chat_id,
            "text": content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=30)
            if resp.status_code == 200 and resp.json().get("ok"):
                print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功")
                if i < len(batches):
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
            else:
                print(f"{log_prefix}第 {i} 批次失败: {resp.json().get('description')}")
                return False
        except Exception as e:
            print(f"{log_prefix}发送出错: {e}")
            return False
    return True