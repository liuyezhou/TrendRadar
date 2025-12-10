# repository/txt_repo.py
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .abc import NewsItemRepository
from ..utils.time import format_date_folder, format_time_filename
from ..utils.file import ensure_directory_exists, clean_title

class TxtNewsRepository(NewsItemRepository):
    def save_batch(self, news_items: List[Dict]) -> None:
        """将一批新闻保存为 .txt 文件（完全复用原始 save_titles_to_file 逻辑）"""
        # 构建 results 和 id_to_name 字典
        results: Dict[str, Dict] = {}
        id_to_name: Dict[str, str] = {}
        failed_ids: List[str] = []

        for item in news_items:
            source_id = item['source_id']
            title = item['title']
            if source_id not in results:
                results[source_id] = {}
                id_to_name[source_id] = item['source_name']
            
            # 构建 title_data（兼容原始结构）
            results[source_id][title] = {
                'ranks': item.get('ranks', []),
                'url': item.get('url', ''),
                'mobileUrl': item.get('mobileUrl', ''),
            }

        # 调用原始逻辑保存文件
        file_path = self._save_titles_to_file(results, id_to_name, failed_ids)
        print(f"[TxtRepo] 标题已保存到: {file_path}")

    def get_all_today(self, platform_ids: Optional[List[str]] = None) -> Tuple[Dict, Dict, Dict]:
        """从当天所有 .txt 文件读取并合并数据（复用原始 read_all_today_titles）"""
        date_folder = format_date_folder()
        txt_dir = Path("output") / date_folder / "txt"
        if not txt_dir.exists():
            return {}, {}, {}

        all_results = {}
        final_id_to_name = {}
        title_info = {}
        files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])

        for file_path in files:
            time_info = file_path.stem
            titles_by_id, file_id_to_name = self._parse_file_titles(file_path)

            # 按 platform_ids 过滤
            if platform_ids is not None:
                filtered_titles_by_id = {}
                filtered_id_to_name = {}
                for source_id, title_data in titles_by_id.items():
                    if source_id in platform_ids:
                        filtered_titles_by_id[source_id] = title_data
                        if source_id in file_id_to_name:
                            filtered_id_to_name[source_id] = file_id_to_name[source_id]
                titles_by_id = filtered_titles_by_id
                file_id_to_name = filtered_id_to_name

            final_id_to_name.update(file_id_to_name)
            for source_id, title_data in titles_by_id.items():
                self._process_source_data(
                    source_id, title_data, time_info, all_results, title_info
                )

        return all_results, final_id_to_name, title_info

    def get_latest_new_titles(self, platform_ids: Optional[List[str]] = None) -> Dict:
        """检测最新批次中的新增标题（复用原始 detect_latest_new_titles）"""
        date_folder = format_date_folder()
        txt_dir = Path("output") / date_folder / "txt"
        if not txt_dir.exists():
            return {}
        
        files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
        if len(files) < 2:
            return {}

        # 解析最新文件
        latest_file = files[-1]
        latest_titles, _ = self._parse_file_titles(latest_file)
        if platform_ids is not None:
            filtered = {sid: data for sid, data in latest_titles.items() if sid in platform_ids}
            latest_titles = filtered

        # 汇总历史标题
        historical_titles = {}
        for file_path in files[:-1]:
            hist_data, _ = self._parse_file_titles(file_path)
            if platform_ids is not None:
                hist_data = {sid: data for sid, data in hist_data.items() if sid in platform_ids}
            for sid, titles in hist_data.items():
                if sid not in historical_titles:
                    historical_titles[sid] = set()
                historical_titles[sid].update(titles.keys())

        # 找出新增
        new_titles = {}
        for sid, latest_data in latest_titles.items():
            hist_set = historical_titles.get(sid, set())
            new_data = {title: data for title, data in latest_data.items() if title not in hist_set}
            if new_data:
                new_titles[sid] = new_data
        return new_titles

    # ========== 以下为原始工具函数的内部实现（私有方法） ==========

    def _save_titles_to_file(self, results: Dict, id_to_name: Dict, failed_ids: List) -> str:
        file_path = self._get_output_path("txt", f"{format_time_filename()}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            for id_value, title_data in results.items():
                name = id_to_name.get(id_value)
                if name and name != id_value:
                    f.write(f"{id_value} | {name}\n")
                else:
                    f.write(f"{id_value}\n")
                sorted_titles = []
                for title, info in title_data.items():
                    cleaned_title = clean_title(title)
                    if isinstance(info, dict):
                        ranks = info.get("ranks", [])
                        url = info.get("url", "")
                        mobile_url = info.get("mobileUrl", "")
                    else:
                        ranks = info if isinstance(info, list) else []
                        url = ""
                        mobile_url = ""
                    rank = ranks[0] if ranks else 1
                    sorted_titles.append((rank, cleaned_title, url, mobile_url))
                sorted_titles.sort(key=lambda x: x[0])
                for rank, cleaned_title, url, mobile_url in sorted_titles:
                    line = f"{rank}. {cleaned_title}"
                    if url:
                        line += f" [URL:{url}]"
                    if mobile_url:
                        line += f" [MOBILE:{mobile_url}]"
                    f.write(line + "\n")
                f.write("\n")
            if failed_ids:
                f.write("==== 以下ID请求失败 ====\n")
                for id_value in failed_ids:
                    f.write(f"{id_value}\n")
        return file_path

    def _parse_file_titles(self, file_path: Path) -> Tuple[Dict, Dict]:
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
                            if ". " in title_part and title_part.split(". ")[0].isdigit():
                                rank_str, title_part = title_part.split(". ", 1)
                                rank = int(rank_str)
                            mobile_url = ""
                            if " [MOBILE:" in title_part:
                                title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                                if mobile_part.endswith("]"):
                                    mobile_url = mobile_part[:-1]
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

    def _process_source_data(
        self, source_id: str, title_data: Dict, time_info: str, all_results: Dict, title_info: Dict
    ) -> None:
        if source_id not in all_results:
            all_results[source_id] = title_data
            if source_id not in title_info:
                title_info[source_id] = {}
            for title, data in title_data.items():
                ranks = data.get("ranks", [])
                url = data.get("url", "")
                mobile_url = data.get("mobileUrl", "")
                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        else:
            for title, data in title_data.items():
                ranks = data.get("ranks", [])
                url = data.get("url", "")
                mobile_url = data.get("mobileUrl", "")
                if title not in all_results[source_id]:
                    all_results[source_id][title] = {
                        "ranks": ranks,
                        "url": url,
                        "mobileUrl": mobile_url,
                    }
                    title_info[source_id][title] = {
                        "first_time": time_info,
                        "last_time": time_info,
                        "count": 1,
                        "ranks": ranks,
                        "url": url,
                        "mobileUrl": mobile_url,
                    }
                else:
                    existing_data = all_results[source_id][title]
                    existing_ranks = existing_data.get("ranks", [])
                    existing_url = existing_data.get("url", "")
                    existing_mobile_url = existing_data.get("mobileUrl", "")
                    merged_ranks = existing_ranks.copy()
                    for rank in ranks:
                        if rank not in merged_ranks:
                            merged_ranks.append(rank)
                    all_results[source_id][title] = {
                        "ranks": merged_ranks,
                        "url": existing_url or url,
                        "mobileUrl": existing_mobile_url or mobile_url,
                    }
                    title_info[source_id][title]["last_time"] = time_info
                    title_info[source_id][title]["ranks"] = merged_ranks
                    title_info[source_id][title]["count"] += 1
                    if not title_info[source_id][title].get("url"):
                        title_info[source_id][title]["url"] = url
                    if not title_info[source_id][title].get("mobileUrl"):
                        title_info[source_id][title]["mobileUrl"] = mobile_url

    def _get_output_path(self, subfolder: str, filename: str) -> str:
        date_folder = format_date_folder()
        output_dir = Path("output") / date_folder / subfolder
        ensure_directory_exists(str(output_dir))
        return str(output_dir / filename)