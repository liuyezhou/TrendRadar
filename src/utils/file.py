# utils/file.py
import os
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from .text import clean_title
from ..repository.abc import NewsItemRepository

from ..utils.time import get_beijing_time
from ..utils.file import clean_title

# 全局 repo 引用（由 main 注入）
_repo: Optional[NewsItemRepository] = None

def set_repository_for_file_utils(repo: NewsItemRepository):
    global _repo
    _repo = repo


def ensure_directory_exists(directory: str):
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)

def get_output_path(subfolder: str, filename: str) -> str:
    """获取输出路径"""
    from .time import format_date_folder  # 避免循环导入
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / subfolder
    ensure_directory_exists(str(output_dir))
    return str(output_dir / filename)

def parse_file_titles(file_path: Path) -> Tuple[Dict, Dict]:
    """解析单个txt文件的标题数据，返回(titles_by_id, id_to_name)"""
    titles_by_id = {}
    id_to_name = {}
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        sections = content.split("\n\n")
        for section in sections:
            if not section.strip() or "==== 以下ID请求失败 ====" in section:
                continue
            lines = section.strip().split("\n")
            if len(lines) < 2:
                continue
            # id | name 或 id
            header_line = lines[0].strip()
            if " | " in header_line:
                parts = header_line.split(" | ", 1)
                source_id = parts[0].strip()
                name = parts[1].strip()
                id_to_name[source_id] = name
            else:
                source_id = header_line
                id_to_name[source_id] = source_id
            titles_by_id[source_id] = {}
            for line in lines[1:]:
                if line.strip():
                    try:
                        title_part = line.strip()
                        rank = None
                        # 提取排名
                        if ". " in title_part and title_part.split(". ")[0].isdigit():
                            rank_str, title_part = title_part.split(". ", 1)
                            rank = int(rank_str)
                        # 提取 MOBILE URL
                        mobile_url = ""
                        if " [MOBILE:" in title_part:
                            title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                            if mobile_part.endswith("]"):
                                mobile_url = mobile_part[:-1]
                        # 提取 URL
                        url = ""
                        if " [URL:" in title_part:
                            title_part, url_part = title_part.rsplit(" [URL:", 1)
                            if url_part.endswith("]"):
                                url = url_part[:-1]
                        title = clean_title(title_part.strip())
                        ranks = [rank] if rank is not None else [1]
                        titles_by_id[source_id][title] = {
                            "ranks": ranks,
                            "url": url,
                            "mobileUrl": mobile_url,
                        }
                    except Exception as e:
                        print(f"解析标题行出错: {line}, 错误: {e}")
    return titles_by_id, id_to_name

def save_titles_to_file(results: Dict, id_to_name: Dict, failed_ids: List) -> str:
    """
    兼容接口：实际调用 repo.save_batch，同时可选生成 .txt 文件（用于调试）
    """
    if _repo is None:
        raise RuntimeError("Repository not set for file utils")

    # 1. 转换为 repo 需要的格式
    news_items = []
    for source_id, titles in results.items():
        source_name = id_to_name[source_id]
        for title, data in titles.items():
            if isinstance(data, dict):
                ranks = data.get("ranks", [])
                url = data.get("url", "")
                mobile_url = data.get("mobileUrl", "")
            else:
                ranks = data if isinstance(data, list) else []
                url = ""
                mobile_url = ""           

            news_items.append({
                'title': clean_title(title),
                'url': url,
                'mobileUrl': mobile_url,
                "ranks": ranks,
                'source_name': source_name,
                'source_id': source_id,
            })


    # 2. 保存到数据库
    try:
        _repo.save_batch(news_items)
        return True
    except:
        print("保存到数据库出错！")

    # # 3. （可选）仍生成 .txt 文件用于调试
    # txt_path = save_titles_to_txt(results, id_to_name, failed_ids)
    # return txt_path  # 保持接口不变
    return False