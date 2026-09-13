# -*- coding: utf-8 -*-
"""数据库后端抽象层"""
from db.backend import DBBackend, SQLiteBackend, PostgresBackend, create_backend
__all__ = ['DBBackend', 'SQLiteBackend', 'PostgresBackend', 'create_backend']
