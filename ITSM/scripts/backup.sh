#!/usr/bin/env bash
# ITSM 数据库备份：pg_dump 自定义格式落 backups/ 目录
# 默认针对 docker-compose.yml（开发）的 postgres；生产改 COMPOSE_FILE=docker-compose.prod.yml
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
cd "$(dirname "$0")/.."

mkdir -p backups
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="backups/itsm_${STAMP}.dump"

docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U itsm -Fc itsm > "$OUT"
echo "备份完成：$OUT"
