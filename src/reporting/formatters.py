# reporting/formatters.py
import re
from typing import Dict, Optional

from ..config import CONFIG
from ..utils.text import html_escape, clean_title
from ..processing.stats import format_rank_display
from ..utils.time import get_beijing_time

__all__ = ["generate_html_report", "render_html_content"]

def format_title_for_platform(
    platform: str, title_data: Dict, show_source: bool = True
) -> str:
    """统一的标题格式化方法"""
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform
    )

    link_url = title_data["mobile_url"] or title_data["url"]

    cleaned_title = clean_title(title_data["title"])

    if platform == "feishu":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']}次)</font>"

        return result

    elif platform == "dingtalk":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    elif platform in ("wework", "bark"):
        # WeWork 和 Bark 使用 markdown 格式
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    elif platform == "telegram":
        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}次)</code>"

        return result

    elif platform == "ntfy":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}次)`"

        return result

    elif platform == "slack":
        # Slack 使用 mrkdwn 格式
        if link_url:
            # Slack 链接格式: <url|text>
            formatted_title = f"<{link_url}|{cleaned_title}>"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        # 排名（使用 * 加粗）
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "slack"
        )
        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}次)`"

        return result

    elif platform == "html":
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html"
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'[{escaped_source_name}] <a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = (
                f'[{escaped_source_name}] <span class="no-link">{escaped_title}</span>'
            )

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}次)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    else:
        return cleaned_title


def render_feishu_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """渲染飞书内容（简化版，仅保留结构）"""
    stats_content = ""
    if report_data["stats"]:
        stats_content += f"📊 **热点词汇统计**\n"
        total_count = len(report_data["stats"])
        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]
            sequence_display = f"<font color='grey'>[{i + 1}/{total_count}]</font>"
            if count >= 10:
                stats_content += f"🔥 {sequence_display} **{word}** : <font color='red'>{count}</font> 条\n"
            elif count >= 5:
                stats_content += f"📈 {sequence_display} **{word}** : <font color='orange'>{count}</font> 条\n"
            else:
                stats_content += f"📌 {sequence_display} **{word}** : {count} 条\n"
            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform("feishu", title_data, show_source=True)
                stats_content += f"  {j}. {formatted_title}\n"
            stats_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n" if i < len(report_data["stats"]) - 1 else ""
    # 新增新闻逻辑（略）
    text_content = stats_content or f"📭 暂无匹配的热点词汇\n"
    now = get_beijing_time()
    text_content += f"\n<font color='grey'>更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"
    if update_info:
        text_content += f"\n<font color='grey'>TrendRadar 发现新版本 {update_info['remote_version']}，当前 {update_info['current_version']}</font>"
    return text_content


def render_dingtalk_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """渲染钉钉内容（简化版）"""
    total_titles = sum(len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0)
    now = get_beijing_time()
    header = f"**总新闻数：** {total_titles}\n**时间：** {now.strftime('%Y-%m-%d %H:%M:%S')}\n**类型：** 热点分析报告\n---\n"
    stats_content = ""
    if report_data["stats"]:
        stats_content += f"📊 **热点词汇统计**\n"
        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]
            sequence_display = f"[{i + 1}/{len(report_data['stats'])}]"
            stats_content += f"🔥 {sequence_display} **{word}** : **{count}** 条\n" if count >= 10 else f"📌 {sequence_display} **{word}** : {count} 条\n"
            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform("dingtalk", title_data, show_source=True)
                stats_content += f"  {j}. {formatted_title}\n"
            stats_content += "\n---\n" if i < len(report_data["stats"]) - 1 else ""
    text_content = header + (stats_content or f"📭 暂无匹配的热点词汇\n")
    text_content += f"\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
    if update_info:
        text_content += f"\n> TrendRadar 发现新版本 **{update_info['remote_version']}**，当前 **{update_info['current_version']}**"
    return text_content

def render_html_content(
    report_data: Dict,
    total_titles: int,
    is_daily_summary: bool = False,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
) -> str:
    """渲染HTML内容（迁移自原始脚本）"""
    from ..utils.time import get_beijing_time
    from ..utils.text import html_escape
    from ..config.loader import CONFIG

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>热点新闻分析</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <style>
            * { box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 16px; background: #fafafa; color: #333; line-height: 1.5; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 16px rgba(0,0,0,0.06); }
            .header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: white; padding: 32px 24px; text-align: center; position: relative; }
            .save-buttons { position: absolute; top: 16px; right: 16px; display: flex; gap: 8px; }
            .save-btn { background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3); color: white; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s ease; backdrop-filter: blur(10px); white-space: nowrap; }
            .save-btn:hover { background: rgba(255,255,255,0.3); border-color: rgba(255,255,255,0.5); transform: translateY(-1px); }
            .save-btn:active { transform: translateY(0); }
            .save-btn:disabled { opacity: 0.6; cursor: not-allowed; }
            .header-title { font-size: 22px; font-weight: 700; margin: 0 0 20px 0; }
            .header-info { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; font-size: 14px; opacity: 0.95; }
            .info-item { text-align: center; }
            .info-label { display: block; font-size: 12px; opacity: 0.8; margin-bottom: 4px; }
            .info-value { font-weight: 600; font-size: 16px; }
            .content { padding: 24px; }
            .word-group { margin-bottom: 40px; }
            .word-group:first-child { margin-top: 0; }
            .word-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; }
            .word-info { display: flex; align-items: center; gap: 12px; }
            .word-name { font-size: 17px; font-weight: 600; color: #1a1a1a; }
            .word-count { color: #666; font-size: 13px; font-weight: 500; }
            .word-count.hot { color: #dc2626; font-weight: 600; }
            .word-count.warm { color: #ea580c; font-weight: 600; }
            .word-index { color: #999; font-size: 12px; }
            .news-item { margin-bottom: 20px; padding: 16px 0; border-bottom: 1px solid #f5f5f5; position: relative; display: flex; gap: 12px; align-items: center; }
            .news-item:last-child { border-bottom: none; }
            .news-item.new::after { content: "NEW"; position: absolute; top: 12px; right: 0; background: #fbbf24; color: #92400e; font-size: 9px; font-weight: 700; padding: 3px 6px; border-radius: 4px; letter-spacing: 0.5px; }
            .news-number { color: #999; font-size: 13px; font-weight: 600; min-width: 20px; text-align: center; flex-shrink: 0; background: #f8f9fa; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; align-self: flex-start; margin-top: 8px; }
            .news-content { flex: 1; min-width: 0; padding-right: 40px; }
            .news-item.new .news-content { padding-right: 50px; }
            .news-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
            .source-name { color: #666; font-size: 12px; font-weight: 500; }
            .rank-num { color: #fff; background: #6b7280; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 10px; min-width: 18px; text-align: center; }
            .rank-num.top { background: #dc2626; }
            .rank-num.high { background: #ea580c; }
            .time-info { color: #999; font-size: 11px; }
            .count-info { color: #059669; font-size: 11px; font-weight: 500; }
            .news-title { font-size: 15px; line-height: 1.4; color: #1a1a1a; margin: 0; }
            .news-link { color: #2563eb; text-decoration: none; }
            .news-link:hover { text-decoration: underline; }
            .news-link:visited { color: #7c3aed; }
            .new-section { margin-top: 40px; padding-top: 24px; border-top: 2px solid #f0f0f0; }
            .new-section-title { color: #1a1a1a; font-size: 16px; font-weight: 600; margin: 0 0 20px 0; }
            .new-source-group { margin-bottom: 24px; }
            .new-source-title { color: #666; font-size: 13px; font-weight: 500; margin: 0 0 12px 0; padding-bottom: 6px; border-bottom: 1px solid #f5f5f5; }
            .new-item { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f9f9f9; }
            .new-item:last-child { border-bottom: none; }
            .new-item-number { color: #999; font-size: 12px; font-weight: 600; min-width: 18px; text-align: center; flex-shrink: 0; background: #f8f9fa; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; }
            .new-item-rank { color: #fff; background: #6b7280; font-size: 10px; font-weight: 700; padding: 3px 6px; border-radius: 8px; min-width: 20px; text-align: center; flex-shrink: 0; }
            .new-item-rank.top { background: #dc2626; }
            .new-item-rank.high { background: #ea580c; }
            .new-item-content { flex: 1; min-width: 0; }
            .new-item-title { font-size: 14px; line-height: 1.4; color: #1a1a1a; margin: 0; }
            .error-section { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin-bottom: 24px; }
            .error-title { color: #dc2626; font-size: 14px; font-weight: 600; margin: 0 0 8px 0; }
            .error-list { list-style: none; padding: 0; margin: 0; }
            .error-item { color: #991b1b; font-size: 13px; padding: 2px 0; font-family: monospace; }
            .footer { margin-top: 32px; padding: 20px 24px; background: #f8f9fa; border-top: 1px solid #e5e7eb; text-align: center; }
            .footer-content { font-size: 13px; color: #6b7280; line-height: 1.6; }
            .footer-link { color: #4f46e5; text-decoration: none; font-weight: 500; transition: color 0.2s ease; }
            .footer-link:hover { color: #7c3aed; text-decoration: underline; }
            .project-name { font-weight: 600; color: #374151; }
            @media (max-width: 480px) {
                body { padding: 12px; }
                .header { padding: 24px 20px; }
                .content { padding: 20px; }
                .footer { padding: 16px 20px; }
                .header-info { grid-template-columns: 1fr; gap: 12px; }
                .news-header { gap: 6px; }
                .news-content { padding-right: 45px; }
                .news-item { gap: 8px; }
                .new-item { gap: 8px; }
                .news-number { width: 20px; height: 20px; font-size: 12px; }
                .save-buttons { position: static; margin-bottom: 16px; display: flex; gap: 8px; justify-content: center; flex-direction: column; width: 100%; }
                .save-btn { width: 100%; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="save-buttons">
                    <button class="save-btn" onclick="saveAsImage()">保存为图片</button>
                    <button class="save-btn" onclick="saveAsMultipleImages()">分段保存</button>
                </div>
                <div class="header-title">热点新闻分析</div>
                <div class="header-info">
    """

    # 报告类型
    if is_daily_summary:
        if mode == "current":
            report_type_text = "当前榜单"
        elif mode == "incremental":
            report_type_text = "增量模式"
        else:
            report_type_text = "当日汇总"
    else:
        report_type_text = "实时分析"
    html += f"""<div class="info-item"><span class="info-label">报告类型</span><span class="info-value">{report_type_text}</span></div>
                    <div class="info-item"><span class="info-label">新闻总数</span><span class="info-value">{total_titles} 条</span></div>"""
    hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])
    html += f"""<div class="info-item"><span class="info-label">热点新闻</span><span class="info-value">{hot_news_count} 条</span></div>"""
    now = get_beijing_time()
    html += f"""<div class="info-item"><span class="info-label">生成时间</span><span class="info-value">{now.strftime("%m-%d %H:%M")}</span></div>
                </div>
            </div>
            <div class="content">
    """
    # 失败ID
    if report_data["failed_ids"]:
        html += f"""
                <div class="error-section">
                    <div class="error-title">⚠️ 请求失败的平台</div>
                    <ul class="error-list">"""
        for id_value in report_data["failed_ids"]:
            html += f'<li class="error-item">{html_escape(id_value)}</li>'
        html += """
                    </ul>
                </div>"""
    # 热点统计
    stats_html = ""
    if report_data["stats"]:
        total_count = len(report_data["stats"])
        for i, stat in enumerate(report_data["stats"], 1):
            count = stat["count"]
            count_class = "hot" if count >= 10 else "warm" if count >= 5 else ""
            escaped_word = html_escape(stat["word"])
            stats_html += f"""
                <div class="word-group">
                    <div class="word-header">
                        <div class="word-info">
                            <div class="word-name">{escaped_word}</div>
                            <div class="word-count {count_class}">{count} 条</div>
                        </div>
                        <div class="word-index">{i}/{total_count}</div>
                    </div>"""
            for j, title_data in enumerate(stat["titles"], 1):
                is_new = title_data.get("is_new", False)
                new_class = "new" if is_new else ""
                stats_html += f"""
                    <div class="news-item {new_class}">
                        <div class="news-number">{j}</div>
                        <div class="news-content">
                            <div class="news-header">
                                <span class="source-name">{html_escape(title_data["source_name"])}</span>"""
                ranks = title_data.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_threshold = title_data.get("rank_threshold", 10)
                    rank_class = "top" if min_rank <= 3 else "high" if min_rank <= rank_threshold else ""
                    rank_text = str(min_rank) if min_rank == max_rank else f"{min_rank}-{max_rank}"
                    stats_html += f'<span class="rank-num {rank_class}">{rank_text}</span>'
                time_display = title_data.get("time_display", "")
                if time_display:
                    simplified_time = time_display.replace(" ~ ", "~").replace("[", "").replace("]", "")
                    stats_html += f'<span class="time-info">{html_escape(simplified_time)}</span>'
                count_info = title_data.get("count", 1)
                if count_info > 1:
                    stats_html += f'<span class="count-info">{count_info}次</span>'
                stats_html += """
                            </div>
                            <div class="news-title">"""
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")
                if link_url:
                    escaped_url = html_escape(link_url)
                    stats_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    stats_html += escaped_title
                stats_html += """
                            </div>
                        </div>
                    </div>"""
            stats_html += "</div>"
    # 新增新闻区域（若非增量模式）
    new_titles_html = ""
    if report_data["new_titles"] and CONFIG.get("REPORT_MODE", "daily") != "incremental":
        new_titles_html += f"""
                <div class="new-section">
                    <div class="new-section-title">本次新增热点 (共 {report_data['total_new_count']} 条)</div>"""
        for source_data in report_data["new_titles"]:
            escaped_source = html_escape(source_data["source_name"])
            titles_count = len(source_data["titles"])
            new_titles_html += f"""
                    <div class="new-source-group">
                        <div class="new-source-title">{escaped_source} · {titles_count}条</div>"""
            for idx, title_data in enumerate(source_data["titles"], 1):
                ranks = title_data.get("ranks", [])
                rank_class = ""
                if ranks:
                    min_rank = min(ranks)
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= title_data.get("rank_threshold", 10):
                        rank_class = "high"
                    rank_text = str(ranks[0]) if len(ranks) == 1 else f"{min(ranks)}-{max(ranks)}"
                else:
                    rank_text = "?"
                new_titles_html += f"""
                        <div class="new-item">
                            <div class="new-item-number">{idx}</div>
                            <div class="new-item-rank {rank_class}">{rank_text}</div>
                            <div class="new-item-content">
                                <div class="new-item-title">"""
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")
                if link_url:
                    escaped_url = html_escape(link_url)
                    new_titles_html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    new_titles_html += escaped_title
                new_titles_html += """
                                </div>
                            </div>
                        </div>"""
            new_titles_html += "</div>"
        new_titles_html += "</div>"
    # 内容顺序
    if CONFIG.get("REVERSE_CONTENT_ORDER", False):
        html += new_titles_html + stats_html
    else:
        html += stats_html + new_titles_html
    # Footer
    html += """
            </div>
            <div class="footer">
                <div class="footer-content">
                    由 <span class="project-name">TrendRadar</span> 生成 · 
                    <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="footer-link">GitHub 开源项目</a>
    """
    if update_info:
        html += f"""
                    <br><span style="color: #ea580c; font-weight: 500;">发现新版本 {update_info['remote_version']}，当前版本 {update_info['current_version']}</span>
        """
    html += """
                </div>
            </div>
        </div>
        <!-- 脚本部分省略以节省篇幅 -->
        <script>
            document.addEventListener('DOMContentLoaded', function() { window.scrollTo(0, 0); });
        </script>
    </body>
    </html>
    """
    return html