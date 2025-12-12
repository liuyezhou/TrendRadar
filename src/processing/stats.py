# processing/stats.py
import os
from typing import Dict, List, Tuple, Optional, Any

from ..config import CONFIG
from .word_matcher import matches_word_groups
from ..core.history import is_first_crawl_today

def calculate_news_weight(
    title_data: Dict[str, Any], rank_threshold: int = CONFIG["RANK_THRESHOLD"]
) -> float:
    """计算新闻权重，用于排序"""
    ranks = title_data.get("ranks", [])
    if not ranks:
        return 0.0
    count = title_data.get("count", len(ranks))
    weight_config = CONFIG["WEIGHT_CONFIG"]
    # 排名权重：Σ(11 - min(rank, 10)) / 出现次数
    rank_scores = []
    for rank in ranks:
        score = 11 - min(rank, 10)
        rank_scores.append(score)
    rank_weight = sum(rank_scores) / len(ranks) if ranks else 0
    # 频次权重：min(出现次数, 10) × 10
    frequency_weight = min(count, 10) * 10
    # 热度加成：高排名次数 / 总出现次数 × 100
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_ratio = high_rank_count / len(ranks) if ranks else 0
    hotness_weight = hotness_ratio * 100
    total_weight = (
        rank_weight * weight_config["RANK_WEIGHT"]
        + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
        + hotness_weight * weight_config["HOTNESS_WEIGHT"]
    )
    return total_weight


def format_time_display(first_time: str, last_time: str) -> str:
    """格式化时间显示"""
    if not first_time:
        return ""
    if first_time == last_time or not last_time:
        return first_time
    else:
        return f"[{first_time} ~ {last_time}]"


def format_rank_display(ranks: List[int], rank_threshold: int, format_type: str) -> str:
    """统一的排名格式化方法"""
    if not ranks:
        return ""
    unique_ranks = sorted(set(ranks))
    min_rank = unique_ranks[0]
    max_rank = unique_ranks[-1]
    if format_type == "html":
        highlight_start = "<font color='red'><strong>"
        highlight_end = "</strong></font>"
    elif format_type == "feishu":
        highlight_start = "<font color='red'>**"
        highlight_end = "**</font>"
    elif format_type == "dingtalk":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "wework":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "telegram":
        highlight_start = "<b>"
        highlight_end = "</b>"
    elif format_type == "slack":
        highlight_start = "*"
        highlight_end = "*"
    else:
        highlight_start = "**"
        highlight_end = "**"
    if min_rank <= rank_threshold:
        if min_rank == max_rank:
            return f"{highlight_start}[{min_rank}]{highlight_end}"
        else:
            return f"{highlight_start}[{min_rank} - {max_rank}]{highlight_end}"
    else:
        if min_rank == max_rank:
            return f"[{min_rank}]"
        else:
            return f"[{min_rank} - {max_rank}]"


def count_word_frequency(
    results: Dict[str, Dict],
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict[str, str],
    title_info: Optional[Dict] = None,
    rank_threshold: int = CONFIG["RANK_THRESHOLD"],
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
    global_filters: Optional[List[str]] = None,
) -> Tuple[List[Dict], int]:
    """统计词频，支持必须词、频率词、过滤词、全局过滤词，并标记新增标题"""
    # 如果没有配置词组，创建一个包含所有新闻的虚拟词组
    if not word_groups:
        print("频率词配置为空，将显示所有新闻")
        word_groups = [{"required": [], "normal": [], "group_key": "全部新闻"}]
        filter_words = []  # 清空过滤词，显示所有新闻
    is_first_today = is_first_crawl_today()
    # 确定处理的数据源和新增标记逻辑
    if mode == "incremental":
        if is_first_today:
            # 增量模式 + 当天第一次：处理所有新闻，都标记为新增
            results_to_process = results
            all_news_are_new = True
        else:
            # 增量模式 + 当天非第一次：只处理新增的新闻
            results_to_process = new_titles if new_titles else {}
            all_news_are_new = True
    elif mode == "current":
        # current 模式：只处理当前时间批次的新闻，但统计信息来自全部历史
        if title_info:
            latest_time = None
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time
            # 只处理 last_time 等于最新时间的新闻
            if latest_time:
                results_to_process = {}
                for source_id, source_titles in results.items():
                    if source_id in title_info:
                        filtered_titles = {}
                        for title, title_data in source_titles.items():
                            if title in title_info[source_id]:
                                info = title_info[source_id][title]
                                if info.get("last_time") == latest_time:
                                    filtered_titles[title] = title_data
                        if filtered_titles:
                            results_to_process[source_id] = filtered_titles
                print(
                    f"当前榜单模式：最新时间 {latest_time}，筛选出 {sum(len(titles) for titles in results_to_process.values())} 条当前榜单新闻"
                )
            else:
                results_to_process = results
        else:
            results_to_process = results
        all_news_are_new = False
    else:
        # 当日汇总模式：处理所有新闻
        results_to_process = results
        all_news_are_new = False
        total_input_news = sum(len(titles) for titles in results.values())
        filter_status = (
            "全部显示"
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻"
            else "频率词过滤"
        )
        print(f"当日汇总模式：处理 {total_input_news} 条新闻，模式：{filter_status}")
    word_stats = {}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0
    if title_info is None:
        title_info = {}
    if new_titles is None:
        new_titles = {}
    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": {}}
    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)
        if source_id not in processed_titles:
            processed_titles[source_id] = {}
        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue
            # 使用统一的匹配逻辑
            matches_frequency_words = matches_word_groups(
                title, word_groups, filter_words, global_filters
            )
            if not matches_frequency_words:
                continue
            # 如果是增量模式或 current 模式第一次，统计匹配的新增新闻数量
            if (mode == "incremental" and all_news_are_new) or (
                mode == "current" and is_first_today
            ):
                matched_new_count += 1
            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")
            # 找到匹配的词组（防御性转换确保类型安全）
            title_lower = str(title).lower() if not isinstance(title, str) else title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]
                # 如果是"全部新闻"模式，所有标题都匹配第一个（唯一的）词组
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻":
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                else:
                    # 原有的匹配逻辑
                    if required_words:
                        all_required_present = all(
                            req_word.lower() in title_lower
                            for req_word in required_words
                        )
                        if not all_required_present:
                            continue
                    if normal_words:
                        any_normal_present = any(
                            normal_word.lower() in title_lower
                            for normal_word in normal_words
                        )
                        if not any_normal_present:
                            continue
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                first_time = ""
                last_time = ""
                count_info = 1
                ranks = source_ranks if source_ranks else []
                url = source_url
                mobile_url = source_mobile_url
                # 对于 current 模式，从历史统计信息中获取完整数据
                if (
                    mode == "current"
                    and title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                elif (
                    title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                if not ranks:
                    ranks = [99]
                time_display = format_time_display(first_time, last_time)
                source_name = id_to_name.get(source_id, source_id)
                # 判断是否为新增
                is_new = False
                if all_news_are_new:
                    # 增量模式下所有处理的新闻都是新增，或者当天第一次的所有新闻都是新增
                    is_new = True
                elif new_titles and source_id in new_titles:
                    # 检查是否在新增列表中
                    new_titles_for_source = new_titles[source_id]
                    is_new = title in new_titles_for_source
                word_stats[group_key]["titles"][source_id].append(
                    {
                        "title": title,
                        "source_name": source_name,
                        "first_time": first_time,
                        "last_time": last_time,
                        "time_display": time_display,
                        "count": count_info,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobileUrl": mobile_url,
                        "is_new": is_new,
                    }
                )
                if source_id not in processed_titles:
                    processed_titles[source_id] = {}
                processed_titles[source_id][title] = True
                break
    # 最后统一打印汇总信息
    if mode == "incremental":
        if is_first_today:
            total_input_news = sum(len(titles) for titles in results.values())
            filter_status = (
                "全部显示"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻"
                else "频率词匹配"
            )
            print(
                f"增量模式：当天第一次爬取，{total_input_news} 条新闻中有 {matched_new_count} 条{filter_status}"
            )
        else:
            if new_titles:
                total_new_count = sum(len(titles) for titles in new_titles.values())
                filter_status = (
                    "全部显示"
                    if len(word_groups) == 1
                    and word_groups[0]["group_key"] == "全部新闻"
                    else "匹配频率词"
                )
                print(
                    f"增量模式：{total_new_count} 条新增新闻中，有 {matched_new_count} 条{filter_status}"
                )
                if matched_new_count == 0 and len(word_groups) > 1:
                    print("增量模式：没有新增新闻匹配频率词，将不会发送通知")
            else:
                print("增量模式：未检测到新增新闻")
    elif mode == "current":
        total_input_news = sum(len(titles) for titles in results_to_process.values())
        if is_first_today:
            filter_status = (
                "全部显示"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻"
                else "频率词匹配"
            )
            print(
                f"当前榜单模式：当天第一次爬取，{total_input_news} 条当前榜单新闻中有 {matched_new_count} 条{filter_status}"
            )
        else:
            matched_count = sum(stat["count"] for stat in word_stats.values())
            filter_status = (
                "全部显示"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻"
                else "频率词匹配"
            )
            print(
                f"当前榜单模式：{total_input_news} 条当前榜单新闻中有 {matched_count} 条{filter_status}"
            )
    stats = []
    # 创建 group_key 到位置和最大数量的映射
    group_key_to_position = {
        group["group_key"]: idx for idx, group in enumerate(word_groups)
    }
    group_key_to_max_count = {
        group["group_key"]: group.get("max_count", 0) for group in word_groups
    }
    for group_key, data in word_stats.items():
        all_titles = []
        for source_id, title_list in data["titles"].items():
            all_titles.extend(title_list)
        # 按权重排序
        sorted_titles = sorted(
            all_titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )
        # 应用最大显示数量限制（优先级：单独配置 > 全局配置）
        group_max_count = group_key_to_max_count.get(group_key, 0)
        if group_max_count == 0:
            # 使用全局配置
            group_max_count = CONFIG.get("MAX_NEWS_PER_KEYWORD", 0)
        if group_max_count > 0:
            sorted_titles = sorted_titles[:group_max_count]
        stats.append(
            {
                "word": group_key,
                "count": data["count"],
                "position": group_key_to_position.get(group_key, 999),
                "titles": sorted_titles,
                "percentage": (
                    round(data["count"] / total_titles * 100, 2)
                    if total_titles > 0
                    else 0
                ),
            }
        )
    # 根据配置选择排序优先级
    if CONFIG.get("SORT_BY_POSITION_FIRST", False):
        # 先按配置位置，再按热点条数
        stats.sort(key=lambda x: (x["position"], -x["count"]))
    else:
        # 先按热点条数，再按配置位置（原逻辑）
        stats.sort(key=lambda x: (-x["count"], x["position"]))
    return stats, total_titles