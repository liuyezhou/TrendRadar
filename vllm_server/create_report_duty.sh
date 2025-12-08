#!/bin/bash
set -e
timedatectl set-timezone Asia/Shanghai

# === 配置区 ===
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"               # 或写死路径，如 "/home/user/myproject"
CRON_SCHEDULE="0 6 * * *"
DOCKER_CMD="$(which docker)"        # 用 `which docker` 确认
LOG_FILE="$(pwd)/vllm-agent-cron.log"

# 检查 docker 是否存在
if [ ! -x "$DOCKER_CMD" ]; then
  echo "Error: $DOCKER_CMD not found. Please check Docker installation."
  exit 1
fi

# 构建完整命令（注意：cron 中 % 需转义，但这里没用到）
CRON_JOB="$CRON_SCHEDULE (cd $PROJECT_DIR && $DOCKER_CMD compose down && $DOCKER_CMD compose build && $DOCKER_CMD compose up --abort-on-container-exit --force-recreate --renew-anon-volumes) >> $LOG_FILE 2>&1"

# 临时文件
TEMP_CRON=$(mktemp)

# 获取当前 crontab（忽略“no crontab”）
crontab -l 2>/dev/null > "$TEMP_CRON" || true

# 避免重复添加
if ! grep -Fq "$CRON_SCHEDULE cd $PROJECT_DIR" "$TEMP_CRON"; then
  echo "$CRON_JOB" >> "$TEMP_CRON"
  crontab "$TEMP_CRON"
  echo "✅ Cron job added:"
  echo "   $CRON_JOB"
else
  echo "⚠️  Cron job already exists."
fi

rm -f "$TEMP_CRON"