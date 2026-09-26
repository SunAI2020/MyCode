@echo off
chcp 65001 >nul
title ITSM 一键启动
echo ==================================================
echo    IT运维集中管控平台  一键启动
echo ==================================================

echo [1/3] 启动数据库（PostgreSQL / Redis / Elasticsearch）...
docker compose up -d
timeout /t 5 /nobreak >nul

echo [2/3] 启动后端（新窗口，端口 8000，默认仅本机访问）...
REM 如需手机局域网访问，把 127.0.0.1 改成 0.0.0.0（生产云服务器切勿对公网开放 8000）
start "ITSM后端" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [3/3] 启动前端（新窗口，端口 5173）...
start "ITSM前端" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo   后端接口文档：http://localhost:8000/docs
echo   前端访问地址：http://localhost:5173
echo   关闭时请直接关闭对应命令行窗口。
echo ==================================================
