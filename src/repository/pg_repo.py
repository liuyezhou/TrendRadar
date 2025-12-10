# repository/pg_repo.py
from typing import List, Dict, Optional, Tuple
import psycopg
from psycopg.rows import dict_row
from .abc import NewsItemRepository
from ..utils.time import get_beijing_time

class PostgreSQLNewsRepository(NewsItemRepository):
    def __init__(self, db_url: str):
        self.db_url = db_url
        self._init_db()

    def _get_conn(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def _init_db(self):
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS news_items (
                        id BIGSERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        url TEXT,
                        mobile_url TEXT,
                        source_name TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        crawl_count INTEGER NOT NULL DEFAULT 1,
                        rank INT[], 
                        category TEXT,
                        summary TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_news_source_title ON news_items (source_id, title);
                    CREATE INDEX IF NOT EXISTS idx_news_created ON news_items (created_at DESC);
                """)
                conn.commit()

    def save_batch(self, news_items: List[Dict]) -> None:
        """用于保存爬取的每日新闻标题"""
        now = get_beijing_time()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                for item in news_items:
                    new_ranks = item.get('ranks', [])  # 本次抓取的排名列表
                    
                    # 尝试更新（合并 ranks）
                    cur.execute("""
                        UPDATE news_items
                        SET 
                            crawl_count = crawl_count + 1,
                            rank = ARRAY(
                                SELECT DISTINCT UNNEST(rank || %s)
                                ORDER BY 1
                            ),
                            updated_at = %s,
                            url = COALESCE(%s, url),
                            mobile_url = COALESCE(%s, mobile_url)
                        WHERE source_id = %s AND title = %s
                        RETURNING id
                    """, (new_ranks, now, item.get('url'), item.get('mobileUrl'), 
                        item['source_id'], item['title']))
                    
                    if cur.fetchone() is None:
                        # 不存在，插入新记录
                        cur.execute("""
                            INSERT INTO news_items (
                                title, url, mobile_url, source_name, source_id,
                                rank, category, summary, created_at, updated_at
                            ) VALUES (
                                %(title)s, %(url)s, %(mobile_url)s, %(source_name)s, %(source_id)s,
                                %(ranks)s, NULL, NULL, %(now)s, %(now)s
                            )
                        """, {
                            'title': item['title'],
                            'url': item.get('url'),
                            'mobile_url': item.get('mobileUrl'),
                            'source_name': item['source_name'],
                            'source_id': item['source_id'],
                            'ranks': new_ranks,  # 直接存 list → int[]
                            'now': now
                        })

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
        """检测最新批次中的新增标题（对比历史）"""
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                # 获取今天所有标题集合
                where_clause = "created_at >= CURRENT_DATE"
                params = platform_ids or []
                if platform_ids:
                    placeholders = ','.join(['%s'] * len(platform_ids))
                    where_clause += f" AND source_id = ANY(ARRAY[{placeholders}])"

                cur.execute(f"SELECT source_id, title FROM news_items WHERE {where_clause}", params)
                all_today = set((r['source_id'], r['title']) for r in cur.fetchall())

                # 获取历史标题（昨天及之前）
                cur.execute(f"SELECT source_id, title FROM news_items WHERE created_at < CURRENT_DATE")
                historical = set((r['source_id'], r['title']) for r in cur.fetchall())

                # 新增 = 今天 - 历史
                new_set = all_today - historical

                # 构建返回结构
                new_titles = {}
                for sid, title in new_set:
                    if sid not in new_titles:
                        new_titles[sid] = {}
                    # 查询完整数据
                    cur.execute("""
                        SELECT url, mobile_url, crawl_count
                        FROM news_items
                        WHERE source_id = %s AND title = %s AND created_at >= CURRENT_DATE
                        ORDER BY created_at DESC LIMIT 1
                    """, (sid, title))
                    row = cur.fetchone()
                    new_titles[sid][title] = {
                        'ranks': [row['crawl_count']] if row else [1],
                        'url': row['url'] if row else '',
                        'mobileUrl': row['mobile_url'] if row else '',
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