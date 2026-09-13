# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — AI漏洞扫描系统 Pro v1.0（onedir 打包，GUI 入口 main.py）

注意：
- 数据库文件不打入包内，打包后由 database.py 的 frozen 分支定位到 EXE 同目录读取/写入，
  发布时另行复制 *.db 到 EXE 同目录。
- matplotlib 必须保留（仪表盘图表依赖），numpy 为其依赖自动带入。
"""
import os

project_dir = os.path.abspath(SPECPATH)

datas = []
assets_dir = os.path.join(project_dir, 'assets')
if os.path.exists(assets_dir):
    datas.append((assets_dir, 'assets'))

# 合规检查条款目录（等保/关基/数据安全/176号）——打包为 _MEIPASS 回退资源，
# 运行时 controls_dir() 仍优先读 EXE 同目录的 compliance_controls（用户可扩充）
compliance_controls_dir = os.path.join(project_dir, 'compliance_controls')
if os.path.exists(compliance_controls_dir):
    datas.append((compliance_controls_dir, 'compliance_controls'))

# 交付文档（帮助菜单 → 交付文档）：打包为 _MEIPASS 回退资源，
# 运行时 _docs_dir() 仍优先读 EXE 同目录的 文档/（可增删）
docs_dir = os.path.join(project_dir, '文档')
if os.path.exists(docs_dir):
    datas.append((docs_dir, '文档'))

hiddenimports = [
    'nmap',                              # scanner_engine 函数内惰性导入
    'weasyprint',                        # report_converter 函数内惰性导入（PDF）
    'docx',                              # report_converter 函数内惰性导入（Word）
    'matplotlib.backends.backend_qt5agg',  # 动态指定 Qt5Agg 后端
]

excludes = [
    'tkinter',
    'jedi', 'IPython', 'ipykernel',
    'notebook', 'jupyterlab', 'django',
    'celery', 'redis', 'kafka',
    'tensorflow', 'torch', 'transformers',
    'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebEngineCore',
]

a = Analysis(
    [os.path.join(project_dir, 'main.py')],
    pathex=[project_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI漏洞扫描系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AI漏洞扫描系统',
)
