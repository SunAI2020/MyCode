#!/usr/bin/env bash
# ITSM 数据库备份：pg_dump 自定义格式落 backups/ 目录
# 默认针对 docker-compose.yml（开发）的 postgres；生产改 COMPOSE_FILE=docker-compose.prod.yml
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
cd "$(dirname "$0")/.."

# 备份含敏感数据：收紧文件权限（目录 0700、文件 0600）
umask 077
install -d -m 700 backups
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="backups/itsm_${STAMP}.dump"

docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U itsm -Fc itsm > "$OUT"
chmod 600 "$OUT"
echo "备份完成：$OUT"
