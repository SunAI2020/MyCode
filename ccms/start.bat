@echo off
chcp 65001 >nul
title CCMS 一键启动

echo.
echo   ╔══════════════════════════════════════════╗
echo   ║     CCMS - Claude Code Management       ║
echo   ║          一键启动脚本                     ║
echo   ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ──────────────────────────────────────
:: 1. 检查 Docker
:: ──────────────────────────────────────
echo [1/4] 检查 Docker 环境...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker Desktop 未启动，请先启动 Docker
    pause
    exit /b 1
)
echo        Docker 已就绪

:: ──────────────────────────────────────
:: 2. 启动 PostgreSQL & Redis
:: ──────────────────────────────────────
echo.
echo [2/4] 启动 PostgreSQL 和 Redis 容器...
docker-compose up -d
if %errorlevel% neq 0 (
    echo [错误] 容器启动失败
    pause
    exit /b 1
)
echo        PostgreSQL ^(5432^) 和 Redis ^(6379^) 已启动

:: ──────────────────────────────────────
:: 3. 安装 Python 依赖（如需要）
:: ──────────────────────────────────────
echo.
echo [3/4] 检查 Python 依赖...
poetry --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Poetry，请先安装: pip install poetry
    pause
    exit /b 1
)
poetry install --no-interaction --no-root
if %errorlevel% neq 0 (
    echo [警告] poetry install 出现问题，尝试更新锁文件...
    poetry lock --no-interaction
    poetry install --no-interaction --no-root
)

:: ──────────────────────────────────────
:: 4. 启动后端 & 前端
:: ──────────────────────────────────────
echo.
echo [4/4] 启动后端和前端服务...

:: 启动后端（新窗口）
start "CCMS - Backend :8000" cmd /c "cd /d "%~dp0" && poetry run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: 等待后端先起来
echo        等待后端启动...
timeout /t 3 /nobreak >nul

:: 启动前端（新窗口）
start "CCMS - Frontend :5173" cmd /c "cd /d "%~dp0frontend" && npx vite --host 0.0.0.0 --port 5173"

:: ──────────────────────────────────────
:: 完成
:: ──────────────────────────────────────
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║         全部启动完成!                     ║
echo   ╠══════════════════════════════════════════╣
echo   ║  后端 API     http://localhost:8000      ║
echo   ║  API 文档     http://localhost:8000/api/docs║
echo   ║  前端界面     http://localhost:5173      ║
echo   ╠══════════════════════════════════════════╣
echo   ║  关闭窗口即可停止对应服务                 ║
echo   ╚══════════════════════════════════════════╝
echo.

pause
