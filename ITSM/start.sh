#!/usr/bin/env bash
# ITSM 一键启动（Linux / macOS）
set -euo pipefail

cd "$(dirname "$0")"

echo "启动数据库..."
docker compose up -d
sleep 5

echo "启动后端（端口 8000，默认仅本机访问）..."
# 如需手机局域网访问，把 127.0.0.1 改成 0.0.0.0（生产云服务器切勿对公网开放 8000）
(cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &

echo "启动前端（端口 5173）..."
cd frontend
npm run dev
