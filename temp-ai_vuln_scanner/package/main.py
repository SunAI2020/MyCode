# -*- coding: utf-8 -*-
import sys
import os

# 强制添加当前目录到路径
_current = os.path.dirname(os.path.abspath(__file__))
if _current not in sys.path:
    sys.path.insert(0, _current)

# 启动GUI
if __name__ == '__main__':
    from main_window import MainWindow
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setFont(QFont('Microsoft YaHei', 10))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())