# notification/manager.py
import os
from typing import Dict, List, Optional
from ..config import CONFIG
from ..utils.time import get_beijing_time
from .push_record import PushRecordManager
from ..reporting import prepare_report_data

# 导入各渠道推送函数
from .channels.feishu import send_to_feishu
from .channels.dingtalk import send_to_dingtalk
from .channels.wework import send_to_wework
from .channels.telegram import send_to_telegram
from .channels.email import send_to_email
from .channels.ntfy import send_to_ntfy
from .channels.bark import send_to_bark
from .channels.slack import send_to_slack

# 多账号工具函数（从 config 模块导入）
from ..config import (
    parse_multi_account_config,
    validate_paired_configs,
    limit_accounts,
    get_account_at_index,
)


def send_to_notifications(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    report_type: str = "当日汇总",
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
) -> Dict[str, bool]:
    """发送数据到多个通知平台（支持多账号）"""
    results = {}
    max_accounts = CONFIG["MAX_ACCOUNTS_PER_CHANNEL"]

    # 推送窗口控制
    if CONFIG["PUSH_WINDOW"]["ENABLED"]:
        push_manager = PushRecordManager()
        time_range_start = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["START"]
        time_range_end = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["END"]
        if not push_manager.is_in_time_range(time_range_start, time_range_end):
            now = get_beijing_time()
            print(f"推送窗口控制：当前时间 {now.strftime('%H:%M')} 不在推送时间窗口 {time_range_start}-{time_range_end} 内，跳过推送")
            return results
        if CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"]:
            if push_manager.has_pushed_today():
                print(f"推送窗口控制：今天已推送过，跳过本次推送")
                return results
            else:
                print(f"推送窗口控制：今天首次推送")

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)
    update_info_to_send = update_info if CONFIG["SHOW_VERSION_UPDATE"] else None

    # === 飞书 ===
    feishu_urls = parse_multi_account_config(CONFIG["FEISHU_WEBHOOK_URL"])
    if feishu_urls:
        feishu_urls = limit_accounts(feishu_urls, max_accounts, "飞书")
        feishu_results = []
        for i, url in enumerate(feishu_urls):
            if url:
                account_label = f"账号{i+1}" if len(feishu_urls) > 1 else ""
                result = send_to_feishu(url, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                feishu_results.append(result)
        results["feishu"] = any(feishu_results)

    # === 飞书外部群 ===
    feishu_outside_urls = parse_multi_account_config(CONFIG["FEISHU_OUTSIDE_WEBHOOK_URL"])
    if feishu_outside_urls:
        feishu_outside_urls = limit_accounts(feishu_outside_urls, max_accounts, "飞书")
        feishu_results = []
        for i, url in enumerate(feishu_outside_urls):
            if url:
                account_label = f"账号{i+1}" if len(feishu_outside_urls) > 1 else ""
                result = send_to_feishu(url, report_data, report_type, update_info_to_send, proxy_url, mode, account_label, use_compatiable_format=True)
                feishu_results.append(result)
        results["feishu_outside"] = any(feishu_results)

    # === 钉钉 ===
    dingtalk_urls = parse_multi_account_config(CONFIG["DINGTALK_WEBHOOK_URL"])
    if dingtalk_urls:
        dingtalk_urls = limit_accounts(dingtalk_urls, max_accounts, "钉钉")
        dingtalk_results = []
        for i, url in enumerate(dingtalk_urls):
            if url:
                account_label = f"账号{i+1}" if len(dingtalk_urls) > 1 else ""
                result = send_to_dingtalk(url, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                dingtalk_results.append(result)
        results["dingtalk"] = any(dingtalk_results)

    # === 企业微信 ===
    wework_urls = parse_multi_account_config(CONFIG["WEWORK_WEBHOOK_URL"])
    if wework_urls:
        wework_urls = limit_accounts(wework_urls, max_accounts, "企业微信")
        wework_results = []
        for i, url in enumerate(wework_urls):
            if url:
                account_label = f"账号{i+1}" if len(wework_urls) > 1 else ""
                result = send_to_wework(url, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                wework_results.append(result)
        results["wework"] = any(wework_results)

    # === Telegram ===
    telegram_tokens = parse_multi_account_config(CONFIG["TELEGRAM_BOT_TOKEN"])
    telegram_chat_ids = parse_multi_account_config(CONFIG["TELEGRAM_CHAT_ID"])
    if telegram_tokens and telegram_chat_ids:
        valid, count = validate_paired_configs(
            {"bot_token": telegram_tokens, "chat_id": telegram_chat_ids},
            "Telegram",
            required_keys=["bot_token", "chat_id"]
        )
        if valid and count > 0:
            telegram_tokens = limit_accounts(telegram_tokens, max_accounts, "Telegram")
            telegram_chat_ids = telegram_chat_ids[:len(telegram_tokens)]
            telegram_results = []
            for i in range(len(telegram_tokens)):
                token = telegram_tokens[i]
                chat_id = telegram_chat_ids[i]
                if token and chat_id:
                    account_label = f"账号{i+1}" if len(telegram_tokens) > 1 else ""
                    result = send_to_telegram(token, chat_id, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                    telegram_results.append(result)
            results["telegram"] = any(telegram_results)

    # === ntfy ===
    ntfy_server_url = CONFIG["NTFY_SERVER_URL"]
    ntfy_topics = parse_multi_account_config(CONFIG["NTFY_TOPIC"])
    ntfy_tokens = parse_multi_account_config(CONFIG["NTFY_TOKEN"])
    if ntfy_server_url and ntfy_topics:
        if ntfy_tokens and len(ntfy_tokens) != len(ntfy_topics):
            print(f"❌ ntfy 配置错误：topic 与 token 数量不一致，跳过推送")
        else:
            ntfy_topics = limit_accounts(ntfy_topics, max_accounts, "ntfy")
            if ntfy_tokens:
                ntfy_tokens = ntfy_tokens[:len(ntfy_topics)]
            ntfy_results = []
            for i, topic in enumerate(ntfy_topics):
                if topic:
                    token = get_account_at_index(ntfy_tokens, i, "")
                    account_label = f"账号{i+1}" if len(ntfy_topics) > 1 else ""
                    result = send_to_ntfy(ntfy_server_url, topic, token, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                    ntfy_results.append(result)
            results["ntfy"] = any(ntfy_results)

    # === Bark ===
    bark_urls = parse_multi_account_config(CONFIG["BARK_URL"])
    if bark_urls:
        bark_urls = limit_accounts(bark_urls, max_accounts, "Bark")
        bark_results = []
        for i, url in enumerate(bark_urls):
            if url:
                account_label = f"账号{i+1}" if len(bark_urls) > 1 else ""
                result = send_to_bark(url, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                bark_results.append(result)
        results["bark"] = any(bark_results)

    # === Slack ===
    slack_urls = parse_multi_account_config(CONFIG["SLACK_WEBHOOK_URL"])
    if slack_urls:
        slack_urls = limit_accounts(slack_urls, max_accounts, "Slack")
        slack_results = []
        for i, url in enumerate(slack_urls):
            if url:
                account_label = f"账号{i+1}" if len(slack_urls) > 1 else ""
                result = send_to_slack(url, report_data, report_type, update_info_to_send, proxy_url, mode, account_label)
                slack_results.append(result)
        results["slack"] = any(slack_results)

    # === 邮件 ===
    email_from = CONFIG["EMAIL_FROM"]
    email_password = CONFIG["EMAIL_PASSWORD"]
    email_to = CONFIG["EMAIL_TO"]
    email_smtp_server = CONFIG.get("EMAIL_SMTP_SERVER", "")
    email_smtp_port = CONFIG.get("EMAIL_SMTP_PORT", "")
    if email_from and email_password and email_to:
        results["email"] = send_to_email(
            email_from, email_password, email_to, report_type, html_file_path,
            email_smtp_server, email_smtp_port
        )

    if not results:
        print("未配置任何通知渠道，跳过通知发送")

    # 记录推送
    if CONFIG["PUSH_WINDOW"]["ENABLED"] and CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"] and any(results.values()):
        push_manager = PushRecordManager()
        push_manager.record_push(report_type)

    return results