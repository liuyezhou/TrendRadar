# config/loader.py
import os
from pathlib import Path
import yaml
from typing import Dict, List, Optional, Tuple
from .constants import SMTP_CONFIGS

# === 多账号推送工具函数 ===
def parse_multi_account_config(config_value: str, separator: str = ";") -> List[str]:
    """
    解析多账号配置，返回账号列表

    Args:
        config_value: 配置值字符串，多个账号用分隔符分隔
        separator: 分隔符，默认为 ;

    Returns:
        账号列表，空字符串会被保留（用于占位）
    """
    if not config_value:
        return []
    # 保留空字符串用于占位（如 ";token2" 表示第一个账号无token）
    accounts = [acc.strip() for acc in config_value.split(separator)]
    # 过滤掉全部为空的情况
    if all(not acc for acc in accounts):
        return []
    return accounts

def validate_paired_configs(
    configs: Dict[str, List[str]],
    channel_name: str,
    required_keys: Optional[List[str]] = None
) -> Tuple[bool, int]:
    """
    验证配对配置的数量是否一致

    Args:
        configs: 配置字典，key 为配置名，value 为账号列表
        channel_name: 渠道名称，用于日志输出
        required_keys: 必须有值的配置项列表

    Returns:
        (是否验证通过, 账号数量)
    """
    # 过滤掉空列表
    non_empty_configs = {k: v for k, v in configs.items() if v}

    if not non_empty_configs:
        return True, 0

    # 检查必须项
    if required_keys:
        for key in required_keys:
            if key not in non_empty_configs or not non_empty_configs[key]:
                return True, 0  # 必须项为空，视为未配置

    # 获取所有非空配置的长度
    lengths = {k: len(v) for k, v in non_empty_configs.items()}
    unique_lengths = set(lengths.values())

    if len(unique_lengths) > 1:
        print(f"❌ {channel_name} 配置错误：配对配置数量不一致，将跳过该渠道推送")
        for key, length in lengths.items():
            print(f"   - {key}: {length} 个")
        return False, 0

    return True, list(unique_lengths)[0] if unique_lengths else 0


def limit_accounts(
    accounts: List[str],
    max_count: int,
    channel_name: str
) -> List[str]:
    """
    限制账号数量

    Args:
        accounts: 账号列表
        max_count: 最大账号数量
        channel_name: 渠道名称，用于日志输出

    Returns:
        限制后的账号列表
    """
    if len(accounts) > max_count:
        print(f"⚠️ {channel_name} 配置了 {len(accounts)} 个账号，超过最大限制 {max_count}，只使用前 {max_count} 个")
        print(f"   ⚠️ 警告：如果您是 fork 用户，过多账号可能导致 GitHub Actions 运行时间过长，存在账号风险")
        return accounts[:max_count]
    return accounts

def get_account_at_index(accounts: List[str], index: int, default: str = "") -> str:
    """
    安全获取指定索引的账号值

    Args:
        accounts: 账号列表
        index: 索引
        default: 默认值

    Returns:
        账号值或默认值
    """
    if index < len(accounts):
        return accounts[index] if accounts[index] else default
    return default


# === 配置管理 ===
def load_config():
    """加载配置文件"""
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"配置文件加载成功: {config_path}")

    # 构建配置
    config = {
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "REPORT_MODE": os.environ.get("REPORT_MODE", "").strip()
        or config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],
        "SORT_BY_POSITION_FIRST": os.environ.get("SORT_BY_POSITION_FIRST", "").strip().lower()
        in ("true", "1")
        if os.environ.get("SORT_BY_POSITION_FIRST", "").strip()
        else config_data["report"].get("sort_by_position_first", False),
        "MAX_NEWS_PER_KEYWORD": int(
            os.environ.get("MAX_NEWS_PER_KEYWORD", "").strip() or "0"
        )
        or config_data["report"].get("max_news_per_keyword", 0),
        "REVERSE_CONTENT_ORDER": os.environ.get("REVERSE_CONTENT_ORDER", "").strip().lower()
        in ("true", "1")
        if os.environ.get("REVERSE_CONTENT_ORDER", "").strip()
        else config_data["report"].get("reverse_content_order", False),
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": os.environ.get("ENABLE_CRAWLER", "").strip().lower()
        in ("true", "1")
        if os.environ.get("ENABLE_CRAWLER", "").strip()
        else config_data["crawler"]["enable_crawler"],
        "ENABLE_NOTIFICATION": os.environ.get("ENABLE_NOTIFICATION", "").strip().lower()
        in ("true", "1")
        if os.environ.get("ENABLE_NOTIFICATION", "").strip()
        else config_data["notification"]["enable_notification"],
        "MESSAGE_BATCH_SIZE": config_data["notification"]["message_batch_size"],
        "DINGTALK_BATCH_SIZE": config_data["notification"].get(
            "dingtalk_batch_size", 20000
        ),
        "FEISHU_BATCH_SIZE": config_data["notification"].get("feishu_batch_size", 29000),
        "BARK_BATCH_SIZE": config_data["notification"].get("bark_batch_size", 3600),
        "SLACK_BATCH_SIZE": config_data["notification"].get("slack_batch_size", 4000),
        "BATCH_SEND_INTERVAL": config_data["notification"]["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": config_data["notification"][
            "feishu_message_separator"
        ],
        # 多账号配置
        "MAX_ACCOUNTS_PER_CHANNEL": int(
            os.environ.get("MAX_ACCOUNTS_PER_CHANNEL", "").strip() or "0"
        )
        or config_data["notification"].get("max_accounts_per_channel", 3),
        "PUSH_WINDOW": {
            "ENABLED": os.environ.get("PUSH_WINDOW_ENABLED", "").strip().lower()
            in ("true", "1")
            if os.environ.get("PUSH_WINDOW_ENABLED", "").strip()
            else config_data["notification"]
            .get("push_window", {})
            .get("enabled", False),
            "TIME_RANGE": {
                "START": os.environ.get("PUSH_WINDOW_START", "").strip()
                or config_data["notification"]
                .get("push_window", {})
                .get("time_range", {})
                .get("start", "08:00"),
                "END": os.environ.get("PUSH_WINDOW_END", "").strip()
                or config_data["notification"]
                .get("push_window", {})
                .get("time_range", {})
                .get("end", "22:00"),
            },
            "ONCE_PER_DAY": os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip().lower()
            in ("true", "1")
            if os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip()
            else config_data["notification"]
            .get("push_window", {})
            .get("once_per_day", True),
            "RECORD_RETENTION_DAYS": int(
                os.environ.get("PUSH_WINDOW_RETENTION_DAYS", "").strip() or "0"
            )
            or config_data["notification"]
            .get("push_window", {})
            .get("push_record_retention_days", 7),
        },
        "WEIGHT_CONFIG": {
            "RANK_WEIGHT": config_data["weight"]["rank_weight"],
            "FREQUENCY_WEIGHT": config_data["weight"]["frequency_weight"],
            "HOTNESS_WEIGHT": config_data["weight"]["hotness_weight"],
        },
        "PLATFORMS": config_data["platforms"],
    }

    # 通知渠道配置（环境变量优先）
    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})

    config["FEISHU_WEBHOOK_URL"] = os.environ.get(
        "FEISHU_WEBHOOK_URL", ""
    ).strip() or webhooks.get("feishu_url", "")
    config["FEISHU_OUTSIDE_WEBHOOK_URL"] = os.environ.get(
        "FEISHU_OUTSIDE_WEBHOOK_URL", ""
    ).strip() or webhooks.get("feishu_outside_url", "")
    config["DINGTALK_WEBHOOK_URL"] = os.environ.get(
        "DINGTALK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("dingtalk_url", "")
    config["WEWORK_WEBHOOK_URL"] = os.environ.get(
        "WEWORK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("wework_url", "")
    config["WEWORK_MSG_TYPE"] = os.environ.get(
        "WEWORK_MSG_TYPE", ""
    ).strip() or webhooks.get("wework_msg_type", "markdown")
    config["TELEGRAM_BOT_TOKEN"] = os.environ.get(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip() or webhooks.get("telegram_bot_token", "")
    config["TELEGRAM_CHAT_ID"] = os.environ.get(
        "TELEGRAM_CHAT_ID", ""
    ).strip() or webhooks.get("telegram_chat_id", "")

    # 邮件配置
    config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", "").strip() or webhooks.get(
        "email_from", ""
    )
    config["EMAIL_PASSWORD"] = os.environ.get(
        "EMAIL_PASSWORD", ""
    ).strip() or webhooks.get("email_password", "")
    config["EMAIL_TO"] = os.environ.get("EMAIL_TO", "").strip() or webhooks.get(
        "email_to", ""
    )
    config["EMAIL_SMTP_SERVER"] = os.environ.get(
        "EMAIL_SMTP_SERVER", ""
    ).strip() or webhooks.get("email_smtp_server", "")
    config["EMAIL_SMTP_PORT"] = os.environ.get(
        "EMAIL_SMTP_PORT", ""
    ).strip() or webhooks.get("email_smtp_port", "")

    # ntfy配置
    config["NTFY_SERVER_URL"] = (
        os.environ.get("NTFY_SERVER_URL", "").strip()
        or webhooks.get("ntfy_server_url")
        or "https://ntfy.sh"
    )
    config["NTFY_TOPIC"] = os.environ.get("NTFY_TOPIC", "").strip() or webhooks.get(
        "ntfy_topic", ""
    )
    config["NTFY_TOKEN"] = os.environ.get("NTFY_TOKEN", "").strip() or webhooks.get(
        "ntfy_token", ""
    )

    # Bark配置
    config["BARK_URL"] = os.environ.get("BARK_URL", "").strip() or webhooks.get(
        "bark_url", ""
    )

    # Slack配置
    config["SLACK_WEBHOOK_URL"] = os.environ.get("SLACK_WEBHOOK_URL", "").strip() or webhooks.get(
        "slack_webhook_url", ""
    )

    # 输出配置来源信息
    notification_sources = []
    max_accounts = config["MAX_ACCOUNTS_PER_CHANNEL"]

    if config["FEISHU_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["FEISHU_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("FEISHU_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"飞书({source})")
    if config["FEISHU_OUTSIDE_WEBHOOK_URL"]:
        source = "环境变量" if os.environ.get("FEISHU_OUTSIDE_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"飞书外部群({source})")
    if config["DINGTALK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["DINGTALK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("DINGTALK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"钉钉({source}, {count}个账号)")
    if config["WEWORK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["WEWORK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("WEWORK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"企业微信({source}, {count}个账号)")
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        tokens = parse_multi_account_config(config["TELEGRAM_BOT_TOKEN"])
        chat_ids = parse_multi_account_config(config["TELEGRAM_CHAT_ID"])
        # 验证数量一致性
        valid, count = validate_paired_configs(
            {"bot_token": tokens, "chat_id": chat_ids},
            "Telegram",
            required_keys=["bot_token", "chat_id"]
        )
        if valid and count > 0:
            count = min(count, max_accounts)
            token_source = "环境变量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
            notification_sources.append(f"Telegram({token_source}, {count}个账号)")
    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "环境变量" if os.environ.get("EMAIL_FROM") else "配置文件"
        notification_sources.append(f"邮件({from_source})")

    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        topics = parse_multi_account_config(config["NTFY_TOPIC"])
        tokens = parse_multi_account_config(config["NTFY_TOKEN"])
        # ntfy 的 token 是可选的，但如果配置了，数量必须与 topic 一致
        if tokens:
            valid, count = validate_paired_configs(
                {"topic": topics, "token": tokens},
                "ntfy"
            )
            if valid and count > 0:
                count = min(count, max_accounts)
                server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
                notification_sources.append(f"ntfy({server_source}, {count}个账号)")
        else:
            count = min(len(topics), max_accounts)
            server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
            notification_sources.append(f"ntfy({server_source}, {count}个账号)")

    if config["BARK_URL"]:
        accounts = parse_multi_account_config(config["BARK_URL"])
        count = min(len(accounts), max_accounts)
        bark_source = "环境变量" if os.environ.get("BARK_URL") else "配置文件"
        notification_sources.append(f"Bark({bark_source}, {count}个账号)")

    if config["SLACK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["SLACK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        slack_source = "环境变量" if os.environ.get("SLACK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"Slack({slack_source}, {count}个账号)")

    if notification_sources:
        print(f"通知渠道配置来源: {', '.join(notification_sources)}")
        print(f"每个渠道最大账号数: {max_accounts}")
    else:
        print("未配置任何通知渠道")

    return config

def _print_notification_sources(config: dict):
    """内部函数：打印通知渠道来源（原逻辑迁移）"""
    notification_sources = []
    max_accounts = config["MAX_ACCOUNTS_PER_CHANNEL"]
    if config["FEISHU_WEBHOOK_URL"]:
        source = "环境变量" if os.environ.get("FEISHU_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"飞书({source})")
    if config["FEISHU_OUTSIDE_WEBHOOK_URL"]:
        source = "环境变量" if os.environ.get("FEISHU_OUTSIDE_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"飞书外部群({source})")
    if config["DINGTALK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["DINGTALK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("DINGTALK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"钉钉({source}, {count}个账号)")
    if config["WEWORK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["WEWORK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        source = "环境变量" if os.environ.get("WEWORK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"企业微信({source}, {count}个账号)")
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        tokens = parse_multi_account_config(config["TELEGRAM_BOT_TOKEN"])
        chat_ids = parse_multi_account_config(config["TELEGRAM_CHAT_ID"])
        valid, count = validate_paired_configs(
            {"bot_token": tokens, "chat_id": chat_ids}, "Telegram", required_keys=["bot_token", "chat_id"]
        )
        if valid and count > 0:
            count = min(count, max_accounts)
            token_source = "环境变量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
            notification_sources.append(f"Telegram({token_source}, {count}个账号)")
    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "环境变量" if os.environ.get("EMAIL_FROM") else "配置文件"
        notification_sources.append(f"邮件({from_source})")
    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        topics = parse_multi_account_config(config["NTFY_TOPIC"])
        tokens = parse_multi_account_config(config["NTFY_TOKEN"])
        if tokens:
            valid, count = validate_paired_configs({"topic": topics, "token": tokens}, "ntfy")
            if valid and count > 0:
                count = min(count, max_accounts)
                server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
                notification_sources.append(f"ntfy({server_source}, {count}个账号)")
        else:
            count = min(len(topics), max_accounts)
            server_source = "环境变量" if os.environ.get("NTFY_SERVER_URL") else "配置文件"
            notification_sources.append(f"ntfy({server_source}, {count}个账号)")
    if config["BARK_URL"]:
        accounts = parse_multi_account_config(config["BARK_URL"])
        count = min(len(accounts), max_accounts)
        bark_source = "环境变量" if os.environ.get("BARK_URL") else "配置文件"
        notification_sources.append(f"Bark({bark_source}, {count}个账号)")
    if config["SLACK_WEBHOOK_URL"]:
        accounts = parse_multi_account_config(config["SLACK_WEBHOOK_URL"])
        count = min(len(accounts), max_accounts)
        slack_source = "环境变量" if os.environ.get("SLACK_WEBHOOK_URL") else "配置文件"
        notification_sources.append(f"Slack({slack_source}, {count}个账号)")
    if notification_sources:
        print(f"通知渠道配置来源: {', '.join(notification_sources)}")
        print(f"每个渠道最大账号数: {max_accounts}")
    else:
        print("未配置任何通知渠道")