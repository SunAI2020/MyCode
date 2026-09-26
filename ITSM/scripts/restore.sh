#!/usr/bin/env bash
# ITSM 数据库恢复：pg_restore --clean --if-exists
# 用法：bash scripts/restore.sh backups/itsm_xxx.dump
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
cd "$(dirname "$0")/.."

if [ "$#" -ne 1 ]; then
  echo "用法: bash scripts/restore.sh backups/itsm_xxx.dump" >&2
  exit 1
fi
DUMP="$1"

docker compose -f "$COMPOSE_FILE" exec -T postgres pg_restore -U itsm -d itsm --clean --if-exists < "$DUMP"
echo "恢复完成：$DUMP"
