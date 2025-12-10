# notification/channels/dingtalk.py
import requests
import time
from typing import Dict, Optional
from ...config import CONFIG
from ...utils.time import get_beijing_time
from ...reporting import split_content_into_batches, add_batch_headers, render_dingtalk_content, get_max_batch_header_size


def send_to_dingtalk(
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
    log_prefix = f"钉钉{account_label}" if account_label else "钉钉"

    dingtalk_batch_size = CONFIG.get("DINGTALK_BATCH_SIZE", 20000)
    header_reserve = get_max_batch_header_size("dingtalk")
    batches = split_content_into_batches(
        report_data, "dingtalk", update_info, max_bytes=dingtalk_batch_size - header_reserve, mode=mode
    )
    batches = add_batch_headers(batches, "dingtalk", dingtalk_batch_size)

    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")
    for i, content in enumerate(batches, 1):
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"TrendRadar 热点分析报告 - {report_type}",
                "text": content,
            },
        }
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