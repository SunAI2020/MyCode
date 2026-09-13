# -*- coding: utf-8 -*-
# AI Vuln Scanner Pro - PyInstaller hooks
from PyInstaller.utils.hooks import collect_data_files, collect_all

# 收集PyQt5
hiddenimports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'sqlite3',
    'requests',
    'schedule',
    'json',
    'logging',
    'datetime',
]

# 收集数据文件
datas = collect_data_files('PyQt5.QtCore', include_py_files=True)

# 收集所有PyQt5模块
collect_all('PyQt5')