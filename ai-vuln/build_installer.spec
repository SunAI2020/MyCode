# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for AI漏洞扫描系统 Pro v1.0
输出目录: d:\vuln
"""
import os

project_dir = os.path.abspath(SPECPATH)
output_dir = r'd:\vuln'

# 收集数据文件
datas = []

# 资源文件 (logo等)
assets_dir = os.path.join(project_dir, 'assets')
if os.path.exists(assets_dir):
    datas.append((assets_dir, 'assets'))

# 数据库文件 (打包预置空库)
for db_file in ['cve_database.db', 'scan_results.db', 'threat_intel.db',
                'audit_results.db', 'assets_system.db']:
    db_path = os.path.join(project_dir, db_file)
    if os.path.exists(db_path):
        datas.append((db_path, '.'))

# 隐式导入 — PyInstaller 无法自动检测的包
hiddenimports = [
    'PyQt5.sip',
    'PyQt5.QtPrintSupport',
    'anthropic',
    'anthropic.types',
    'python_nmap',
    'weasyprint',
    'docx',
    'lxml',
    'lxml.etree',
    'cffi',
    'cssselect2',
    'tinycss2',
    'html5lib',
    'pyphen',
    'PIL',
    'Crypto',
    'Cryptodome',
    'nmap',
]

# 排除无关模块以减小体积
excludes = [
    'tkinter', 'unittest', 'test', 'pydoc', 'pdb',
    'matplotlib', 'numpy', 'pandas', 'scipy',
    'jedi', 'IPython', 'ipykernel',
    'notebook', 'jupyterlab', 'django',
    'celery', 'redis', 'kafka',
    'tensorflow', 'torch', 'transformers',
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
