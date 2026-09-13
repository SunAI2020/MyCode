@echo off
chcp 65001 >nul
title AI漏洞扫描系统 Pro - 安装程序

echo ============================================
echo   AI漏洞扫描系统 Pro v1.0 安装程序
echo   山西有信网安科技有限公司 (c)2026
echo ============================================
echo.

REM 获取当前目录
set "APP_DIR=%~dp0"
set "APP_EXE=%APP_DIR%AI漏洞扫描系统.exe"

REM 检查主程序是否存在
if not exist "%APP_EXE%" (
    echo [错误] 未找到主程序: %APP_EXE%
    echo 请确保此脚本位于程序目录中
    pause
    exit /b 1
)

echo [1/3] 检查系统环境...

REM 检查 Nmap (可选，扫描引擎需要)
where nmap >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [提示] 未检测到 Nmap，部分扫描功能将使用内置引擎
    echo        如需完整功能，请安装 Nmap: https://nmap.org/download.html
) else (
    echo [ OK ] Nmap 已安装
)

echo.
echo [2/3] 创建桌面快捷方式...

REM 使用 PowerShell 创建桌面快捷方式
powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$desktop = [Environment]::GetFolderPath('Desktop'); " ^
    "$sc = $ws.CreateShortcut(\"$desktop\AI漏洞扫描系统.lnk\"); " ^
    "$sc.TargetPath = '%APP_EXE%'; " ^
    "$sc.WorkingDirectory = '%APP_DIR%'; " ^
    "$sc.Description = 'AI漏洞扫描系统 Pro v1.0 - 下一代智能漏洞扫描系统'; " ^
    "$sc.IconLocation = '%APP_EXE%,0'; " ^
    "$sc.Save();"

if %ERRORLEVEL% EQU 0 (
    echo [ OK ] 桌面快捷方式已创建
) else (
    echo [失败] 无法创建桌面快捷方式
)

echo.
echo [3/3] 创建开始菜单快捷方式...

powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$startmenu = [Environment]::GetFolderPath('Programs') + '\AI漏洞扫描系统'; " ^
    "if (-not (Test-Path $startmenu)) { New-Item -ItemType Directory -Path $startmenu -Force | Out-Null }; " ^
    "$sc = $ws.CreateShortcut(\"$startmenu\AI漏洞扫描系统.lnk\"); " ^
    "$sc.TargetPath = '%APP_EXE%'; " ^
    "$sc.WorkingDirectory = '%APP_DIR%'; " ^
    "$sc.Description = 'AI漏洞扫描系统 Pro v1.0'; " ^
    "$sc.IconLocation = '%APP_EXE%,0'; " ^
    "$sc.Save();"

if %ERRORLEVEL% EQU 0 (
    echo [ OK ] 开始菜单快捷方式已创建
) else (
    echo [提示] 开始菜单快捷方式创建失败（非致命错误）
)

echo.
echo ============================================
echo   安装完成！
echo   桌面快捷方式: AI漏洞扫描系统
echo   程序目录: %APP_DIR%
echo ============================================
echo.
echo 按任意键启动程序，或关闭此窗口稍后手动启动...

pause >nul

REM 启动程序
if exist "%APP_EXE%" (
    start "" "%APP_EXE%"
)

exit /b 0
