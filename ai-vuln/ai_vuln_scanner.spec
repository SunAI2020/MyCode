# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AI漏洞扫描系统 Pro v1.0
"""

import os

project_dir = os.path.abspath(SPECPATH)

# 收集数据文件
datas = []

# 资源文件
assets_dir = os.path.join(project_dir, 'assets')
if os.path.exists(assets_dir):
    datas.append((assets_dir, 'assets'))

# 数据库文件
for db_file in ['cve_database.db', 'scan_results.db', 'threat_intel.db',
                'audit_results.db', 'assets_system.db']:
    db_path = os.path.join(project_dir, db_file)
    if os.path.exists(db_path):
        datas.append((db_path, '.'))

# 隐式导入
hiddenimports = [
    'PyQt5.sip',
]

# 排除不必要的模块
excludes = [
    'tkinter', 'unittest', 'test', 'pydoc',
    'distutils', 'setuptools', 'pip',
    'matplotlib', 'numpy', 'pandas', 'scipy',
    'jedi', 'IPython', 'ipykernel',
    'notebook', 'jupyterlab', 'django',
    'celery', 'redis', 'kafka',
]

a = Analysis(
    [os.path.join(project_dir, 'main.py')],
    pathex=[],
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
    a.binaries,
    a.datas,
    [],
    name='AI漏洞扫描系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name='AI漏洞扫描系统',
)
