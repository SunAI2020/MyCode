# -*- coding: utf-8 -*-
# AI Vuln Scanner Pro - 入口点
import sys
import os

# 设置路径
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, app_path)

# 运行GUI
if __name__ == '__main__':
    # 直接导入并运行
    sys.modules['main_window'] = __import__('main_window', fromlist=[''])

    from main_window import MainWindow
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont('Microsoft YaHei', 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())