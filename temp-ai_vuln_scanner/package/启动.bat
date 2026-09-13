@echo off
chcp 65001 >nul
echo ========================================
echo   AI Vuln Scanner Pro - 启动器
echo   下一代智能漏洞扫描系统
echo ========================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
pip show PyQt5 >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装PyQt5...
    pip install PyQt5 -q
)
pip show requests >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装requests...
    pip install requests -q
)
pip show schedule >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装schedule...
    pip install schedule -q
)

echo [2/3] 启动程序...
python main.py

if errorlevel 1 (
    echo.
    echo [错误] 程序启动失败
    pause
)