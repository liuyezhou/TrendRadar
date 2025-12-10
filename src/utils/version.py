# utils/version.py
import requests
import os
from typing import Optional, Tuple

def check_version_update(
    current_version: str, version_url: str, proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """检查版本更新"""
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }
        response = requests.get(
            version_url, proxies=proxies, headers=headers, timeout=10
        )
        response.raise_for_status()
        remote_version = response.text.strip()
        print(f"当前版本: {current_version}, 远程版本: {remote_version}")
        # 比较版本
        def parse_version(version_str):
            try:
                parts = version_str.strip().split(".")
                if len(parts) != 3:
                    raise ValueError("版本号格式不正确")
                return int(parts[0]), int(parts[1]), int(parts[2])
            except:
                return 0, 0, 0
        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)
        need_update = current_tuple < remote_tuple
        return need_update, remote_version if need_update else None
    except Exception as e:
        print(f"版本检查失败: {e}")
        return False, None