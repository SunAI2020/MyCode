#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Vuln Scanner Pro - 打包脚本
使用: python build.py
"""
import os
import sys
import shutil
import PyInstaller.__main__

def build():
    """打包应用程序"""
    print("=" * 50)
    print("AI Vuln Scanner Pro - 打包程序")
    print("=" * 50)

    # 清理旧构建
    print("\n[1/4] 清理旧构建...")
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')

    # 创建图标（如果需要）
    print("[2/4] 创建图标...")

    # PyInstaller 命令
    print("[3/4] 运行PyInstaller...")

    PyInstaller.__main__.pyinstaller_run([
        'main.py',
        '--name=AI_Vuln_Scanner_Pro',
        '--onefile',  # 单文件模式
        '--windowed',  # GUI模式（不显示控制台）
        '--icon=NONE',  # Windows默认图标
        '--add-data=reports;reports',  # 包含reports目录
        '--hidden-import=PyQt5',
        '--hidden-import=PyQt5.QtCore',
        '--hidden-import=PyQt5.QtGui',
        '--hidden-import=PyQt5.QtWidgets',
        '--hidden-import=sqlite3',
        '--hidden-import=requests',
        '--hidden-import=schedule',
        '--collect-all=PyQt5',
        '--noconfirm',  # 不询问确认
    ])

    print("[4/4] 完成!")
    print("\n" + "=" * 50)
    print("打包完成!")
    print("可执行文件: dist/AI_Vuln_Scanner_Pro.exe")
    print("=" * 50)


if __name__ == '__main__':
    build()