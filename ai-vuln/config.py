# -*- coding: utf-8 -*-
"""集中配置 — 环境变量驱动，SQLite / PostgreSQL 双后端"""
import os
import sys


def _app_base_dir() -> str:
    """返回应用基础目录：打包后为 EXE 同目录，源码运行时为模块所在目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_BACKEND = os.getenv('DB_BACKEND', 'sqlite')
DB_SQLITE_DIR = os.getenv('DB_SQLITE_DIR', _app_base_dir())

PG_HOST = os.getenv('PG_HOST', 'localhost')
PG_PORT = int(os.getenv('PG_PORT', '5432'))
PG_DATABASE = os.getenv('PG_DATABASE', 'ai_vuln')
PG_USER = os.getenv('PG_USER', 'postgres')
PG_PASSWORD = os.getenv('PG_PASSWORD', '')
PG_POOL_MIN = int(os.getenv('PG_POOL_MIN', '2'))
PG_POOL_MAX = int(os.getenv('PG_POOL_MAX', '10'))

API_HOST = os.getenv('API_HOST', '127.0.0.1')
API_PORT = int(os.getenv('API_PORT', '8000'))
API_KEY = os.getenv('API_KEY', 'changeme-default-key')

APP_COMPANY = '山西有信网安科技有限公司'
APP_VERSION = '2.1.0'
