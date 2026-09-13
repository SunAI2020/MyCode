# -*- coding: utf-8 -*-
"""数据资产暴露面排查系统 - 程序入口"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gui.main_window import MainWindow

if __name__ == "__main__":
    app = MainWindow()
    app.run()
