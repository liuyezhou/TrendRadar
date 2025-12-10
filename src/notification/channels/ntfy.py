# notification/channels/ntfy.py
import requests
import time
from urllib.parse import urlparse
from typing import Dict, Optional
from ...config import CONFIG
from ...reporting import split_content_into_batches, add_batch_headers, get_max_batch_header_size


def send_to_ntfy(
    server_url: str,
    topic: str,
    token: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
) -> bool:
    base_url = server_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    url = f"{base_url}/{topic}"

    report_type_en_map = {
        "当日汇总": "Daily Summary",
        "当前榜单汇总": "Current Ranking",
        "增量更新": "Incremental Update",
        "实时增量": "Realtime Incremental",
        "实时当前榜单": "Realtime Current Ranking",
    }
    report_type_en = report_type_en_map.get(report_type, "News Report")

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Markdown": "yes",
        "Title": report_type_en,
        "Priority": "default",
        "Tags": "news",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    log_prefix = f"ntfy{account_label}" if account_label else "ntfy"

    ntfy_batch_size = 3800
    header_reserve = get_max_batch_header_size("ntfy")
    batches = split_content_into_batches(
        report_data, "ntfy", update_info, max_bytes=ntfy_batch_size - header_reserve, mode=mode
    )
    batches = add_batch_headers(batches, "ntfy", ntfy_batch_size)
    batches = list(reversed(batches))  # 反向推送

    total = len(batches)
    success = 0
    for idx, content in enumerate(batches, 1):
        actual_num = total - idx + 1
        if total > 1:
            headers["Title"] = f"{report_type_en} ({actual_num}/{total})"
        try:
            resp = requests.post(url, headers=headers, data=content.encode("utf-8"), proxies=proxies, timeout=30)
            if resp.status_code == 200:
                success += 1
                if idx < total:
                    time.sleep(2 if "ntfy.sh" in server_url else 1)
            elif resp.status_code == 429:
                time.sleep(10)
                resp = requests.post(url, headers=headers, data=content.encode("utf-8"), proxies=proxies, timeout=30)
                if resp.status_code == 200:
                    success += 1
        except Exception as e:
            print(f"{log_prefix}第 {actual_num} 批次异常: {e}")

    return success > 0