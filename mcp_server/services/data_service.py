"""
数据访问服务

提供统一的数据查询接口,封装数据访问逻辑。
"""

import os
import psycopg
from psycopg.rows import dict_row
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .cache_service import get_cache
from .parser_service import ParserService
from ..utils.errors import DataNotFoundError


class DataService:
    """数据访问服务类"""

    def __init__(self, project_root, db_url: Optional[str] = None):
        """
        初始化数据服务

        Args:
            db_url: PostgreSQL 连接字符串，如 postgresql://user:pass@localhost:5432/db
                    如果未提供，则从环境变量 DATABASE_URL 读取
        """
        self.project_root = project_root
        self.parser = ParserService(project_root)
        self.db_url = db_url
        self.cache = get_cache()

    def _get_conn(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)
    
    def get_latest_news(
        self,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        include_url: bool = False
    ) -> List[Dict]:
        """
        获取最新一批爬取的新闻数据（按 updated_at 最晚的批次）
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # 1. 找出今天最新的 updated_at 时间
                where_clause = "created_at >= CURRENT_DATE"
                params = []
                if platforms:
                    placeholders = ','.join(['%s'] * len(platforms))
                    where_clause += f" AND source_id = ANY(ARRAY[{placeholders}])"
                    params = platforms

                cur.execute(f"""
                    SELECT MAX(updated_at) as latest_time
                    FROM news_items
                    WHERE {where_clause}
                """, params)
                latest_time = cur.fetchone()['latest_time']
                if not latest_time:
                    raise DataNotFoundError("未找到今天的新闻数据")

                # 2. 获取该时间点的所有新闻
                cur.execute(f"""
                    SELECT title, source_id, source_name, rank, url, mobile_url, updated_at
                    FROM news_items
                    WHERE updated_at = %s AND {where_clause}
                    ORDER BY (rank[1]) ASC NULLS LAST
                    LIMIT %s
                """, [latest_time] + params + [limit])

                results = []
                for row in cur.fetchall():
                    # 取第一个排名（rank[1] 对应 SQL 中的 rank[1]）
                    ranks = row['rank'] or []
                    rank = ranks[0] if ranks else 0

                    item = {
                        "title": row['title'],
                        "platform": row['source_id'],
                        "platform_name": row['source_name'],
                        "rank": rank,
                        "timestamp": row['updated_at'].strftime("%Y-%m-%d %H:%M:%S")
                    }
                    if include_url:
                        item["url"] = row['url'] or ""
                        item["mobileUrl"] = row['mobile_url'] or ""
                    results.append(item)

                return results

    def get_news_by_date(
        self,
        target_date: datetime,
        platforms: Optional[List[str]] = None,
        limit: int = 50,
        include_url: bool = False
    ) -> List[Dict]:
        """
        按指定日期获取新闻（按当天所有新闻的首次出现排名排序）
        """
        date_str = target_date.strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                where_clause = "created_at >= %s AND created_at < %s"
                params = [target_date, target_date + timedelta(days=1)]
                if platforms:
                    placeholders = ','.join(['%s'] * len(platforms))
                    where_clause += f" AND source_id = ANY(ARRAY[{placeholders}])"
                    params += platforms

                cur.execute(f"""
                    SELECT title, source_id, source_name, rank, url, mobile_url, crawl_count
                    FROM news_items
                    WHERE {where_clause}
                    ORDER BY (rank[1]) ASC NULLS LAST
                    LIMIT %s
                """, params + [limit])

                results = []
                for row in cur.fetchall():
                    ranks = row['rank'] or []
                    rank = ranks[0] if ranks else 0
                    avg_rank = sum(ranks) / len(ranks) if ranks else 0

                    item = {
                        "title": row['title'],
                        "platform": row['source_id'],
                        "platform_name": row['source_name'],
                        "rank": rank,
                        "avg_rank": round(avg_rank, 2),
                        "count": row['crawl_count'],
                        "date": date_str
                    }
                    if include_url:
                        item["url"] = row['url'] or ""
                        item["mobileUrl"] = row['mobile_url'] or ""
                    results.append(item)

                if not results:
                    raise DataNotFoundError(f"未找到 {date_str} 的新闻数据")

                return results
    
    def search_news_by_keyword(
        self,
        keyword: str,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        platforms: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        按关键词搜索新闻
        """
        if date_range:
            start_date, end_date = date_range
        else:
            now = datetime.now()
            start_date = end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                where_clause = "title ILIKE %s"
                params = [f"%{keyword}%"]

                # 日期范围
                where_clause += " AND created_at >= %s AND created_at <= %s"
                params += [start_date, end_date + timedelta(days=1)]

                if platforms:
                    placeholders = ','.join(['%s'] * len(platforms))
                    where_clause += f" AND source_id = ANY(ARRAY[{placeholders}])"
                    params += platforms

                # 查询匹配新闻
                cur.execute(f"""
                    SELECT title, source_id, source_name, rank, url, mobile_url, created_at
                    FROM news_items
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                """, params)

                results = []
                platform_distribution = Counter()
                total_ranks = []

                for row in cur.fetchall():
                    ranks = row['rank'] or []
                    avg_rank = sum(ranks) / len(ranks) if ranks else 0
                    total_ranks.extend(ranks)

                    item = {
                        "title": row['title'],
                        "platform": row['source_id'],
                        "platform_name": row['source_name'],
                        "ranks": ranks,
                        "count": len(ranks),
                        "avg_rank": round(avg_rank, 2),
                        "url": row['url'] or "",
                        "mobileUrl": row['mobile_url'] or "",
                        "date": row['created_at'].strftime("%Y-%m-%d")
                    }
                    results.append(item)
                    platform_distribution[row['source_id']] += 1

                if not results:
                    raise DataNotFoundError(
                        f"未找到包含关键词 '{keyword}' 的新闻",
                        suggestion="请尝试其他关键词或扩大日期范围"
                    )

                avg_rank = sum(total_ranks) / len(total_ranks) if total_ranks else 0
                total_found = len(results)
                if limit and limit > 0:
                    results = results[:limit]

                return {
                    "results": results,
                    "total": len(results),
                    "total_found": total_found,
                    "statistics": {
                        "platform_distribution": dict(platform_distribution),
                        "avg_rank": round(avg_rank, 2),
                        "keyword": keyword
                    }
                }

    def get_trending_topics(
        self,
        top_n: int = 10,
        mode: str = "current"
    ) -> Dict:
        """
        基于 PostgreSQL 数据库实现的热点词频统计
        Args:
            top_n: 返回 TOP N 词
            mode: "daily"（全天）或 "current"（最新批次）
        """
        if mode not in ("daily", "current"):
            raise ValueError("mode 必须是 'daily' 或 'current'")

        # 1. 加载 frequency_words 配置
        try:
            word_groups, filter_words, global_filters = self._load_frequency_words()
        except Exception as e:
            raise DataNotFoundError(f"加载 frequency_words 失败: {e}")

        # 2. 构建 SQL 查询条件
        today = datetime.now().strftime("%Y-%m-%d")
        if mode == "current":
            # 只查最新一批（latest updated_at）
            sql = """
                SELECT title, source_id
                FROM news_items
                WHERE created_at >= %s
                  AND updated_at = (
                      SELECT MAX(updated_at)
                      FROM news_items
                      WHERE created_at >= %s
                  )
            """
            params = [today, today]
        else:  # mode == "daily"
            sql = "SELECT title, source_id FROM news_items WHERE created_at >= %s"
            params = [today]

        # 3. 执行查询
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        if not rows:
            raise DataNotFoundError("今日无新闻数据")

        # 4. 词频统计
        word_frequency = Counter()
        keyword_to_titles = {}

        for row in rows:
            title = row['title']
            title_lower = title.lower()

            # 全局过滤
            if global_filters and any(gf.lower() in title_lower for gf in global_filters):
                continue

            # 过滤词
            if any(fw.lower() in title_lower for fw in filter_words):
                continue

            # 词组匹配
            for group in word_groups:
                required = group["required"]
                normal = group["normal"]

                if required and not all(rw.lower() in title_lower for rw in required):
                    continue
                if normal and not any(nw.lower() in title_lower for nw in normal):
                    continue

                # 匹配成功，统计所有关键词
                for word in (required + normal):
                    if word:
                        word_frequency[word] += 1
                        if word not in keyword_to_titles:
                            keyword_to_titles[word] = set()
                        keyword_to_titles[word].add(title)

        # 5. 构建结果
        top_keywords = word_frequency.most_common(top_n)
        topics = []
        for keyword, freq in top_keywords:
            topics.append({
                "keyword": keyword,
                "frequency": freq,
                "matched_news": len(keyword_to_titles[keyword]),
                "trend": "stable",
                "weight_score": 0.0
            })

        return {
            "topics": topics,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "total_keywords": len(word_frequency),
            "description": "当日累计统计" if mode == "daily" else "最新一批统计"
        }
    
    def _get_mode_description(self, mode: str) -> str:
        """获取模式描述"""
        descriptions = {
            "daily": "当日累计统计",
            "current": "最新一批统计"
        }
        return descriptions.get(mode, "未知模式")

    def get_current_config(self, section: str = "all") -> Dict:
        """
        获取当前系统配置

        Args:
            section: 配置节 - all/crawler/push/keywords/weights

        Returns:
            配置字典

        Raises:
            FileParseError: 配置文件解析错误
        """
        # 尝试从缓存获取
        cache_key = f"config:{section}"
        cached = self.cache.get(cache_key, ttl=3600)  # 1小时缓存
        if cached:
            return cached

        # 解析配置文件
        config_data = self.parser.parse_yaml_config()
        word_groups = self.parser.parse_frequency_words()

        # 根据section返回对应配置
        if section == "all" or section == "crawler":
            crawler_config = {
                "enable_crawler": config_data.get("crawler", {}).get("enable_crawler", True),
                "use_proxy": config_data.get("crawler", {}).get("use_proxy", False),
                "request_interval": config_data.get("crawler", {}).get("request_interval", 1),
                "retry_times": 3,
                "platforms": [p["id"] for p in config_data.get("platforms", [])]
            }

        if section == "all" or section == "push":
            push_config = {
                "enable_notification": config_data.get("notification", {}).get("enable_notification", True),
                "enabled_channels": [],
                "message_batch_size": config_data.get("notification", {}).get("message_batch_size", 20),
                "push_window": config_data.get("notification", {}).get("push_window", {})
            }

            # 检测已配置的通知渠道
            webhooks = config_data.get("notification", {}).get("webhooks", {})
            if webhooks.get("feishu_url"):
                push_config["enabled_channels"].append("feishu")
            if webhooks.get("dingtalk_url"):
                push_config["enabled_channels"].append("dingtalk")
            if webhooks.get("wework_url"):
                push_config["enabled_channels"].append("wework")

        if section == "all" or section == "keywords":
            keywords_config = {
                "word_groups": word_groups,
                "total_groups": len(word_groups)
            }

        if section == "all" or section == "weights":
            weights_config = {
                "rank_weight": config_data.get("weight", {}).get("rank_weight", 0.6),
                "frequency_weight": config_data.get("weight", {}).get("frequency_weight", 0.3),
                "hotness_weight": config_data.get("weight", {}).get("hotness_weight", 0.1)
            }

        # 组装结果
        if section == "all":
            result = {
                "crawler": crawler_config,
                "push": push_config,
                "keywords": keywords_config,
                "weights": weights_config
            }
        elif section == "crawler":
            result = crawler_config
        elif section == "push":
            result = push_config
        elif section == "keywords":
            result = keywords_config
        elif section == "weights":
            result = weights_config
        else:
            result = {}

        # 缓存结果
        self.cache.set(cache_key, result)

        return result

    def get_available_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        获取数据库中实际可用的日期范围
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MIN(created_at), MAX(created_at) FROM news_items")
                row = cur.fetchone()
                min_time = row[0]
                max_time = row[1]
                if min_time is None:
                    return (None, None)
                # 转为日期（不带时分秒）
                earliest = min_time.replace(hour=0, minute=0, second=0, microsecond=0)
                latest = max_time.replace(hour=0, minute=0, second=0, microsecond=0)
                return (earliest, latest)
            

    def get_system_status(self) -> Dict:
        """
        获取系统运行状态（基于 PostgreSQL 数据库）

        Returns:
            系统状态字典
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # 1. 从 news_items 表获取数据统计
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_news,
                        MIN(created_at) as oldest_record,
                        MAX(created_at) as latest_record,
                        pg_total_relation_size('news_items') as table_size
                    FROM news_items
                """)
                news_stats = cur.fetchone()

                total_news = news_stats['total_news'] or 0
                oldest_record = news_stats['oldest_record']
                latest_record = news_stats['latest_record']
                news_table_size = news_stats['table_size'] or 0

                # 2. 从 daily_summaries 表获取摘要表大小（如有）
                try:
                    cur.execute("SELECT pg_total_relation_size('daily_summaries')")
                    summary_size = cur.fetchone()[0] or 0
                except:
                    summary_size = 0  # 表可能不存在

                total_storage = news_table_size + summary_size

                # 3. 转换日期格式
                oldest_str = oldest_record.strftime("%Y-%m-%d") if oldest_record else None
                latest_str = latest_record.strftime("%Y-%m-%d") if latest_record else None

        # 4. 获取版本信息（保留文件读取，因版本文件与数据库无关）
        version = "unknown"
        version_file = self.project_root / "version"
        if version_file.exists():
            try:
                with open(version_file, "r") as f:
                    version = f.read().strip()
            except:
                pass

        # 5. 构建返回结果
        return {
            "system": {
                "version": version,
                "project_root": str(self.project_root),
                "database": self.db_url.split("@")[-1] if self.db_url else "unknown"
            },
            "data": {
                "total_news": total_news,
                "total_storage": f"{total_storage / 1024 / 1024:.2f} MB",
                "oldest_record": oldest_str,
                "latest_record": latest_str,
            },
            "cache": getattr(self, 'cache', None).get_stats() if hasattr(self, 'cache') else {},
            "health": "healthy" if total_news > 0 else "no_data"
        }