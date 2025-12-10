# utils/db.py
import os
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

class DBManager:
    _instance = None
    _pool = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_pool()
        return cls._instance

    def _init_pool(self):
        # 从环境变量或配置读取 DB 配置
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            # 默认本地开发配置
            db_url = "postgresql://tr:tr@localhost:5432/trendradar"

        # 解析 URL（简单版）
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        self._pool = SimpleConnectionPool(
            1, 4,  # minconn=1, maxconn=4
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5432,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
        self._create_tables()

    def _create_tables(self):
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS news_items (
            id BIGSERIAL PRIMARY KEY,
            crawl_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source_id TEXT NOT NULL,
            source_name TEXT,
            title TEXT NOT NULL,
            url TEXT,
            mobile_url TEXT,
            ranks INT[],
            is_new BOOLEAN DEFAULT FALSE,
            report_mode TEXT,
            -- 用于后续快速聚合
            date_key DATE NOT NULL DEFAULT CURRENT_DATE
        );
        CREATE INDEX IF NOT EXISTS idx_news_date_source ON news_items (date_key, source_id);
        CREATE INDEX IF NOT EXISTS idx_news_title ON news_items USING GIN (to_tsvector('simple', title));
        """
        with self._pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_sql)
                conn.commit()

    def get_connection(self):
        return self._pool.getconn()

    def return_connection(self, conn):
        self._pool.putconn(conn)

    def save_news_batch(self, news_items):
        """保存一批新闻条目"""
        with self._pool.getconn() as conn:
            with conn.cursor() as cur:
                sql = """
                INSERT INTO news_items (
                    crawl_time, source_id, source_name, title,
                    url, mobile_url, ranks, is_new, report_mode
                ) VALUES (
                    %(crawl_time)s, %(source_id)s, %(source_name)s, %(title)s,
                    %(url)s, %(mobile_url)s, %(ranks)s, %(is_new)s, %(report_mode)s
                )
                """
                cur.executemany(sql, news_items)
                conn.commit()

    def get_all_today_news(self, source_ids=None):
        """获取今天所有新闻（可按 source_id 过滤）"""
        with self._pool.getconn() as conn:
            with conn.cursor() as cur:
                if source_ids:
                    placeholders = ','.join(['%s'] * len(source_ids))
                    cur.execute(f"""
                        SELECT * FROM news_items
                        WHERE date_key = CURRENT_DATE
                          AND source_id = ANY(ARRAY[{placeholders}])
                        ORDER BY crawl_time, source_id, title
                    """, source_ids)
                else:
                    cur.execute("""
                        SELECT * FROM news_items
                        WHERE date_key = CURRENT_DATE
                        ORDER BY crawl_time, source_id, title
                    """)
                return cur.fetchall()

    def get_latest_new_titles(self, source_ids=None):
        """检测最新一批中的新增标题（对比之前所有）"""
        with self._pool.getconn() as conn:
            with conn.cursor() as cur:
                # 获取最新 crawl_time
                if source_ids:
                    placeholders = ','.join(['%s'] * len(source_ids))
                    cur.execute(f"""
                        SELECT MAX(crawl_time) FROM news_items
                        WHERE date_key = CURRENT_DATE
                          AND source_id = ANY(ARRAY[{placeholders}])
                    """, source_ids)
                else:
                    cur.execute("SELECT MAX(crawl_time) FROM news_items WHERE date_key = CURRENT_DATE")
                latest_time = cur.fetchone()[0]
                if not latest_time:
                    return {}

                # 获取最新批次的所有标题
                if source_sites:
                    cur.execute(f"""
                        SELECT source_id, title, url, mobile_url, ranks
                        FROM news_items
                        WHERE date_key = CURRENT_DATE
                          AND crawl_time = %s
                          AND source_id = ANY(ARRAY[{placeholders}])
                    """, [latest_time] + source_ids)
                else:
                    cur.execute("""
                        SELECT source_id, title, url, mobile_url, ranks
                        FROM news_items
                        WHERE date_key = CURRENT_DATE AND crawl_time = %s
                    """, (latest_time,))
                latest_rows = cur.fetchall()

                # 获取之前所有标题集合
                if source_ids:
                    cur.execute(f"""
                        SELECT DISTINCT source_id, title
                        FROM news_items
                        WHERE date_key = CURRENT_DATE
                          AND crawl_time < %s
                          AND source_id = ANY(ARRAY[{placeholders}])
                    """, [latest_time] + source_ids)
                else:
                    cur.execute("""
                        SELECT DISTINCT source_id, title
                        FROM news_items
                        WHERE date_key = CURRENT_DATE AND crawl_time < %s
                    """, (latest_time,))
                historical_set = set((row['source_id'], row['title']) for row in cur.fetchall())

                # 找出新增
                new_titles = {}
                for row in latest_rows:
                    key = (row['source_id'], row['title'])
                    if key not in historical_set:
                        if row['source_id'] not in new_titles:
                            new_titles[row['source_id']] = {}
                        new_titles[row['source_id']][row['title']] = {
                            'ranks': row['ranks'],
                            'url': row['url'],
                            'mobile_url': row['mobile_url'],
                        }
                return new_titles