# repository/pg_repo.py
from typing import List, Dict, Optional, Tuple
import psycopg
from psycopg.rows import dict_row
from .abc import NewsItemRepository
from ..utils.time import get_beijing_time

class PostgreSQLNewsRepository(NewsItemRepository):
    def __init__(self, db_url: str):
        self.db_url = db_url

    def _get_conn(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def save_batch(self, news_items: List[Dict]) -> int:
        """
        保存一批新闻，返回本次使用的 batch_id
        - 新闻首次出现：使用当前 batch_id
        - 新闻已存在：保留原始 batch_id，仅更新 updated_at 和其他字段
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # 1. 获取新批次号
                cur.execute("SELECT nextval('news_batch_seq')")
                batch_id = cur.fetchone()['nextval']

                now = get_beijing_time()
                for item in news_items:
                    cur.execute("""
                        INSERT INTO news_items (
                            title, url, mobile_url, source_name, source_id,
                            crawl_count, rank, batch_id, created_at, updated_at
                        ) VALUES (
                            %(title)s, %(url)s, %(mobile_url)s, %(source_name)s, %(source_id)s,
                            1, %(ranks)s, %(batch_id)s, %(now)s, %(now)s
                        )
                        ON CONFLICT (source_id, title)
                        DO UPDATE SET
                            crawl_count = news_items.crawl_count + 1,
                            rank = news_items.rank || EXCLUDED.rank,
                            updated_at = %(now)s,
                            batch_id = news_items.batch_id 
                    """, {
                        'title': item['title'],
                        'url': item.get('url'),
                        'mobile_url': item.get('mobileUrl'),
                        'source_name': item['source_name'],
                        'source_id': item['source_id'],
                        'ranks': item.get('ranks', []),
                        'batch_id': batch_id,
                        'now': now
                    })
                return batch_id

    def is_first_crawl_today(self) -> bool:
        """
        判断是否是当天第一次爬取（基于数据库）
        Returns:
            True: 今天尚无新闻记录（是首次爬取）
            False: 今天已有新闻
        """
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1
                    FROM news_items
                    WHERE created_at >= CURRENT_DATE
                    LIMIT 1
                """)
                return cur.fetchone() is None           
            
    def get_all_today(self, platform_ids: Optional[List[str]] = None) -> Tuple[Dict, Dict, Dict]:
        """兼容原始接口：返回 (all_results, id_to_name, title_info)"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                where_clause = "created_at >= CURRENT_DATE"
                params = []
                if platform_ids:
                    placeholders = ','.join(['%s'] * len(platform_ids))
                    where_clause += f" AND source_id = ANY(ARRAY[{placeholders}])"
                    params = platform_ids

                cur.execute(f"""
                    SELECT * FROM news_items
                    WHERE {where_clause}
                    ORDER BY created_at, source_id, title
                """, params)
                rows = cur.fetchall()
        
        # 构建兼容结构
        all_results = {}
        id_to_name = {}
        title_info = {}
        for row in rows:
            sid = row['source_id']
            title = row['title']
            if sid not in all_results:
                all_results[sid] = {}
                id_to_name[sid] = row['source_name']
            if sid not in title_info:
                title_info[sid] = {}

            if title not in all_results[sid]:
                all_results[sid][title] = {
                    'ranks': row['rank'] or [],      # ✅ 从 rank 列读取
                    'url': row['url'] or '',
                    'mobileUrl': row['mobile_url'] or '',
                }
                title_info[sid][title] = {
                    'first_time': row['created_at'].strftime('%H时%M分'),
                    'last_time': row['updated_at'].strftime('%H时%M分'),
                    'count': row['crawl_count'],
                    'ranks': row['rank'] or [],      # ✅ 关键：使用 rank 列
                    'url': row['url'] or '',
                    'mobileUrl': row['mobile_url'] or '',
                }
            else:
                # 合并逻辑（理论上不会发生，因 save_batch 已去重）
                pass

        return all_results, id_to_name, title_info

    def get_latest_new_titles(self, platform_ids: Optional[List[str]] = None) -> Dict:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # 1. 构建 WHERE 条件
                where_clause = "1=1"
                params = []
                if platform_ids:
                    placeholders = ','.join(['%s'] * len(platform_ids))
                    where_clause += f" AND source_id = ANY(ARRAY[{placeholders}])"
                    params = platform_ids

                # 2. 获取最新 batch_id
                cur.execute("SELECT last_value FROM news_batch_seq")
                latest_batch = cur.fetchone()['last_value']

                # 3. 获取最新批次的 (source_id, title)
                cur.execute(f"""
                    SELECT source_id, title
                    FROM news_items
                    WHERE {where_clause} AND batch_id = %s
                """, params + [latest_batch])
                latest_set = set((r['source_id'], r['title']) for r in cur.fetchall())
                if len(latest_set) == 0:
                    return {}
    

                # 6. ✅ 正确查询完整字段
                values_clauses = []
                query_params = [latest_batch]
                for sid, title in latest_set:
                    values_clauses.append("(%s, %s)")
                    query_params.extend([sid, title])

                values_sql = ",".join(values_clauses)
                cur.execute(f"""
                    SELECT source_id, title, url, mobile_url, rank
                    FROM news_items
                    WHERE batch_id = %s
                    AND (source_id, title) = ANY (VALUES {values_sql})
                """, query_params)

                new_titles = {}
                for row in cur.fetchall():
                    sid = row['source_id']
                    if sid not in new_titles:
                        new_titles[sid] = {}
                    new_titles[sid][row['title']] = {
                        'ranks': row['rank'],
                        'url': row['url'] or '',
                        'mobileUrl': row['mobile_url'] or '',
                    }
                return new_titles
            
    # -----------------------------------------
    # ----------- 新闻总结 ---------------------
    # -----------------------------------------
    def save_daily_summary(
        self,
        summary_date: str,          # 格式: "2025-12-09"
        model_name: str,            #
        summary_type: str,
        content: str,
        word_groups: Optional[List[str]] = None,
        news_count: int = 0,
    ) -> int:
        """保存当日新闻总结，返回 summary ID"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO daily_summaries (
                        summary_date, model_name, summary_type, content, word_groups, news_count
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (summary_date, model_name, summary_type)
                    DO UPDATE SET
                        content = EXCLUDED.content,
                        word_groups = EXCLUDED.word_groups,
                        news_count = EXCLUDED.news_count,
                        updated_at = NOW()
                    RETURNING id
                """, (summary_date, model_name, summary_type, content, word_groups, news_count))
                return cur.fetchone()['id']

    def get_daily_summary(
        self,
        summary_date: str,
        model_name: str = "qwen",
        summary_type: str = "daily"
    ) -> Optional[Dict]:
        """获取指定日期的总结"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, summary_date, model_name, summary_type, content, word_groups, news_count, created_at
                    FROM daily_summaries
                    WHERE summary_date = %s AND model_name = %s AND summary_type = %s
                """, (summary_date, model_name, summary_type))
                return cur.fetchone()  # 返回 None 或 dict
    
    def get_recent_summaries(
        self,
        days: int = 7,
        model_name: str = "qwen",
        summary_type: str = "daily"
    ) -> List[Dict]:
        """获取最近 N 天的总结（按日期倒序）"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, summary_date, content, news_count, created_at
                    FROM daily_summaries
                    WHERE summary_date >= CURRENT_DATE - %s
                    AND model_name = %s
                    AND summary_type = %s
                    ORDER BY summary_date DESC
                """, (days, model_name, summary_type))
                return cur.fetchall()


if __name__ == "__main__":
    import os
    db = PostgreSQLNewsRepository(os.getenv("DATABASE_URL"))
    db.get_latest_new_titles()