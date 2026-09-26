#!/usr/bin/env bash
# ITSM 一键启动（Linux / macOS）
set -euo pipefail

cd "$(dirname "$0")"

echo "启动数据库..."
docker compose up -d
sleep 5

echo "启动后端（端口 8000）..."
(cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &

echo "启动前端（端口 5173）..."
cd frontend
npm run dev
