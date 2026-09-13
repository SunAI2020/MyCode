#!/bin/bash
# 漏洞扫描系统 - Logo 设置脚本
# 版权所有：山西有信网安科技有限公司

ASSETS_DIR="./assets"
LOGO_FILE="$ASSETS_DIR/logo.png"

echo "========================================"
echo "  漏洞扫描系统 - Logo 设置工具"
echo "  © 山西有信网安科技有限公司"
echo "========================================"
echo ""

# 创建 assets 目录
if [ ! -d "$ASSETS_DIR" ]; then
    echo "✓ 创建 assets 目录..."
    mkdir -p "$ASSETS_DIR"
fi

# 检查是否已有 logo
if [ -f "$LOGO_FILE" ]; then
    echo "✓ Logo 文件已存在：$LOGO_FILE"
    echo ""
    echo "  如需更换 Logo，请："
    echo "  1. 删除现有文件：rm $LOGO_FILE"
    echo "  2. 将新 Logo 图片复制到：$LOGO_FILE"
else
    echo "⚠ Logo 文件不存在"
    echo ""
    echo "  请将公司商标图片复制到："
    echo "  $LOGO_FILE"
    echo ""
    echo "  例如："
    echo "  cp /path/to/your/logo.png $LOGO_FILE"
    echo ""
    echo "  要求："
    echo "  - 格式：PNG"
    echo "  - 尺寸：建议 200x200 像素"
    echo "  - 支持透明背景"
fi

echo ""
echo "========================================"
echo "  启动 GUI 应用"
echo "========================================"
echo ""
echo "  运行以下命令启动图形界面："
echo "  python3 gui_app.py"
echo ""
echo "  如果没有 Logo 图片，系统会自动显示文字 Logo"
echo ""
