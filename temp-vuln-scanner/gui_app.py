#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漏洞扫描系统 - GUI 启动脚本
版权所有：山西有信网安科技有限公司
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from gui.main_window import main

if __name__ == '__main__':
    main()
