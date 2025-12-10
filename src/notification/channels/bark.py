# notification/channels/bark.py
import requests
import time
from urllib.parse import urlparse
from typing import Dict, Optional
from ...config import CONFIG
from ...reporting import split_content_into_batches, add_batch_headers, get_max_batch_header_size


def send_to_bark(
    bark_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
) -> bool:
    parsed = urlparse(bark_url)
    device_key = parsed.path.strip("/").split("/")[0] if parsed.path else None
    if not device_key:
        print(f"Bark URL 无效: {bark_url}")
        return False
    api_url = f"{parsed.scheme}://{parsed.netloc}/push"

    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    log_prefix = f"Bark{account_label}" if account_label else "Bark"

    bark_batch_size = CONFIG["BARK_BATCH_SIZE"]
    header_reserve = get_max_batch_header_size("bark")
    batches = split_content_into_batches(
        report_data, "bark", update_info, max_bytes=bark_batch_size - header_reserve, mode=mode
    )
    batches = add_batch_headers(batches, "bark", bark_batch_size)
    batches = list(reversed(batches))

    total = len(batches)
    success = 0
    for idx, content in enumerate(batches, 1):
        actual_num = total - idx + 1
        payload = {
            "title": report_type,
            "markdown": content,
            "device_key": device_key,
            "group": "TrendRadar",
            "sound": "default",
            "action": "none",
        }
        try:
            resp = requests.post(api_url, json=payload, proxies=proxies, timeout=30)
            if resp.status_code == 200 and resp.json().get("code") == 200:
                success += 1
                if idx < total:
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
        except Exception as e:
            print(f"{log_prefix}第 {actual_num} 批次异常: {e}")

    return success > 0