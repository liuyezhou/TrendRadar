-- 创建新闻表
CREATE TABLE IF NOT EXISTS news_items (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT,
    mobile_url TEXT,
    source_name TEXT NOT NULL,
    source_id TEXT NOT NULL,
    crawl_count INTEGER NOT NULL DEFAULT 1,
    rank INT[], 
    category TEXT,          -- 可为空
    summary TEXT,           -- 可为空
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_news_url ON news_items(url);
CREATE INDEX idx_news_date ON news_items(updated_at);
CREATE INDEX idx_news_category ON news_items(category);
CREATE INDEX idx_news_source_title ON news_items (source_id, title);
CREATE INDEX idx_news_created ON news_items (created_at DESC);

-- 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_news_articles_modtime
BEFORE UPDATE ON news_items
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- 创建新闻总结表
CREATE TABLE daily_summaries (
    id BIGSERIAL PRIMARY KEY,
    summary_date DATE NOT NULL,                     -- 总结日期（如 2025-12-09）
    model_name TEXT NOT NULL DEFAULT 'qwen3',        -- 模型名称（如 qwen, gemini, gpt-4）
    summary_type TEXT NOT NULL DEFAULT 'daily',     -- 总结类型（daily, current, incremental）
    content TEXT NOT NULL,                          -- 总结内容（Markdown/纯文本）
    word_groups TEXT[],                             -- 涉及的关键词组（可选）
    news_count INTEGER NOT NULL,                    -- 涉及新闻条数
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 确保同一天、同模型、同类型只有一条总结（可选）
    UNIQUE (summary_date, model_name, summary_type)
);
-- 索引优化
CREATE INDEX idx_summaries_date ON daily_summaries (summary_date DESC);
CREATE INDEX idx_summaries_model ON daily_summaries (model_name);

-- 插入示例数据
-- INSERT INTO news_articles (title, url, updated_at, category, summary) VALUES
-- ('中国人工智能发展取得新突破', 'https://example.com/news1', '2025-01-01', '科技', '我国在AI领域取得重大进展...'),
-- ('全球金融市场震荡', 'https://example.com/news2', '2025-01-01', '财经', '受多重因素影响，全球市场波动...'),
-- ('体育赛事精彩纷呈', 'https://example.com/news3', '2025-01-01', NULL, NULL)
-- ON CONFLICT (url) DO NOTHING;