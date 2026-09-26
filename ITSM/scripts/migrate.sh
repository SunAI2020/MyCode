#!/usr/bin/env bash
# ITSM 数据库迁移 + 种子（本地开发；生产在 backend 容器内执行同名命令）
set -euo pipefail

cd "$(dirname "$0")/../backend"

alembic upgrade head
python -m app.db.seed
echo "迁移 + 种子完成"
