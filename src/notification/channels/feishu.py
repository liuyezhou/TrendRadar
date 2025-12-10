# notification/channels/feishu.py
import requests
import time
from typing import Dict, Optional
from ...config import CONFIG
from ...utils.time import get_beijing_time
from ...reporting import split_content_into_batches, add_batch_headers, get_max_batch_header_size


def send_to_feishu(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    account_label: str = "",
    use_compatiable_format=False,
) -> bool:
    """发送到飞书（支持分批发送）"""
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # 日志前缀
    log_prefix = f"飞书{account_label}" if account_label else "飞书"

    # 获取分批内容，使用飞书专用的批次大小
    feishu_batch_size = CONFIG.get("FEISHU_BATCH_SIZE", 29000)
    # 预留批次头部空间，避免添加头部后超限
    header_reserve = get_max_batch_header_size("feishu")
    batches = split_content_into_batches(
        report_data,
        "wework" if use_compatiable_format else "feishu",
        update_info,
        max_bytes=feishu_batch_size - header_reserve,
        mode=mode,
    )

    # 统一添加批次头部（已预留空间，不会超限）
    batches = add_batch_headers(batches, "feishu", feishu_batch_size)

    print(f"{log_prefix}消息分为 {len(batches)} 批次发送 [{report_type}]")

    # 逐批发送
    for i, batch_content in enumerate(batches, 1):
        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"发送{log_prefix}第 {i}/{len(batches)} 批次，大小：{batch_size} 字节 [{report_type}]"
        )

        total_titles = sum(
            len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
        )
        now = get_beijing_time()

        payload = {
            "msg_type": "text",
            "content": {
                "total_titles": total_titles,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "report_type": report_type,
                "text": batch_content,
            },
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                # 检查飞书的响应状态
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    print(f"{log_prefix}第 {i}/{len(batches)} 批次发送成功 [{report_type}]")
                    # 批次间间隔
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    error_msg = result.get("msg") or result.get("StatusMessage", "未知错误")
                    print(
                        f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{error_msg}"
                    )
                    return False
            else:
                print(
                    f"{log_prefix}第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"{log_prefix}第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}")
            return False

    print(f"{log_prefix}所有 {len(batches)} 批次发送完成 [{report_type}]")
    return True

