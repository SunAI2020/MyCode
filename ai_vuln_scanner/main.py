#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下一代智能漏洞扫描系统 Pro v1.0
山西有信网安科技有限公司
Next-Generation AI Vulnerability Scanning System
"""
import sys
import os

# 确保能找到同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QFont


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('AI漏洞扫描系统 Pro')
    app.setOrganizationName('©2026 山西有信网安科技有限公司')

    # 启动画面
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = ''
    for ext in ['.jpg', '.png']:
        p = os.path.join(base_dir, 'assets', f'logo{ext}')
        if os.path.exists(p):
            logo_path = p
            break

    if logo_path:
        splash_pix = QPixmap(logo_path).scaled(400, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        splash = QSplashScreen(splash_pix)
        splash.show()
        splash.showMessage('正在初始化AI漏洞扫描系统...\n©2026 山西有信网安科技有限公司',
                           Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()

    from main_window import MainWindow
    window = MainWindow()

    if logo_path:
        splash.finish(window)

    window.showMaximized()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
