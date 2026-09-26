#!/usr/bin/env bash
# ITSM 一键安装（Linux / macOS）
set -euo pipefail

echo "=================================================="
echo "   IT运维集中管控平台  一键安装（Linux）"
echo "=================================================="

cd "$(dirname "$0")"

command -v docker >/dev/null 2>&1 || { echo "[错误] 请先安装 Docker 与 docker compose"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "[错误] 请先安装 Python 3.13"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[错误] 请先安装 Node.js 20"; exit 1; }

echo "[1/4] 启动数据库与中间件..."
docker compose up -d
sleep 10

echo "[2/4] 配置后端环境变量..."
[ -f backend/.env ] || cp .env.example backend/.env

echo "[3/4] 安装后端依赖并初始化数据库..."
cd backend
python3 -m pip install -r requirements.txt -q
python3 -m alembic upgrade head
python3 -m app.db.seed
cd ..

echo "[4/4] 安装前端依赖..."
cd frontend
npm install
cd ..

echo "=================================================="
echo "安装完成！运行 bash start.sh 启动系统"
echo "默认账号 admin，初始密码见上方 seed 输出"
echo "=================================================="
