@echo off
setlocal
chcp 65001 >nul
title ITSM 一键安装
echo ==================================================
echo    IT运维集中管控平台  一键安装（Windows）
echo ==================================================
echo.

REM ---- 1. 检查 Docker ----
echo [1/6] 检查 Docker...
where docker >nul 2>nul
if errorlevel 1 (
    echo   [错误] 未检测到 Docker，请先安装 Docker Desktop：
    echo          https://www.docker.com/products/docker-desktop/
    echo   安装后请重启电脑再运行本脚本。
    pause
    exit /b 1
)
echo   Docker 已就绪

REM ---- 2. 检查 Python ----
echo [2/6] 检查 Python...
where python >nul 2>nul
if errorlevel 1 (
    echo   [错误] 未检测到 Python，请先安装 Python 3.13：
    echo          https://www.python.org/downloads/
    echo   安装时务必勾选 "Add python.exe to PATH"。
    pause
    exit /b 1
)
echo   Python 已就绪

REM ---- 3. 启动数据库与中间件 ----
echo [3/6] 启动数据库（PostgreSQL / Redis / Elasticsearch）...
docker compose up -d
if errorlevel 1 (
    echo   [错误] 数据库启动失败，请确认 Docker Desktop 正在运行。
    pause
    exit /b 1
)
echo   数据库已启动，等待就绪 10 秒...
timeout /t 10 /nobreak >nul

REM ---- 4. 后端环境变量 ----
echo [4/6] 配置后端环境变量...
if not exist "backend\.env" (
    copy ".env.example" "backend\.env" >nul
    echo   已生成 backend\.env（如需改端口/密码，编辑该文件）
) else (
    echo   backend\.env 已存在，跳过
)

REM ---- 5. 后端依赖 + 迁移 + 种子 ----
echo [5/6] 安装后端依赖并初始化数据库（首次可能耗时）...
cd backend
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo   [错误] 后端依赖安装失败。
    cd ..
    pause
    exit /b 1
)
python -m alembic upgrade head
python -m app.db.seed
cd ..
echo   后端初始化完成（管理员账号 admin，初始密码见上方输出）

REM ---- 6. 前端依赖 ----
echo [6/6] 安装前端依赖（可能耗时数分钟）...
cd frontend
call npm install
if errorlevel 1 (
    echo   [错误] 前端依赖安装失败，请确认已安装 Node.js 20。
    cd ..
    pause
    exit /b 1
)
cd ..
echo   前端依赖安装完成

echo.
echo ==================================================
echo   安装完成！请双击 start.bat 一键启动系统
echo   后端文档：http://localhost:8000/docs
echo   前端页面：http://localhost:5173
echo   默认账号：admin / 初始密码（安装时输出的随机口令）
echo ==================================================
pause
