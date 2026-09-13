#!/usr/bin/env python3
"""
漏洞扫描系统 - 主程序入口
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from cli import main

if __name__ == '__main__':
    main()
