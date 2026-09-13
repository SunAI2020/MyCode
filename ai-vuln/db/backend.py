# -*- coding: utf-8 -*-
"""数据库后端抽象 — ABC + SQLiteBackend + PostgresBackend + 工厂"""
import os
import sqlite3
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)


class DBBackend(ABC):
    """数据库后端抽象基类"""

    @abstractmethod
    def connect(self, db_name: str = '') -> Any:
        """获取连接"""
        ...

    @abstractmethod
    def placeholder(self) -> str:
        """参数占位符: SQLite='?', PG='%s'"""
        ...

    def last_insert_id(self, cursor, table: str = '', pk: str = 'id') -> int:
        return cursor.lastrowid

    @abstractmethod
    def close(self) -> None:
        ...


class SQLiteBackend(DBBackend):
    """SQLite 后端"""

    def __init__(self, base_dir: str = ''):
        self.base_dir = base_dir or os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        self._conns: Dict[str, sqlite3.Connection] = {}

    def connect(self, db_name: str = '') -> sqlite3.Connection:
        if db_name in self._conns:
            return self._conns[db_name]
        path = os.path.join(self.base_dir, db_name)
        conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA temp_store=2")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        self._conns[db_name] = conn
        return conn

    def placeholder(self) -> str:
        return '?'

    def close(self) -> None:
        for c in self._conns.values():
            try: c.close()
            except Exception: pass
        self._conns.clear()


class PostgresBackend(DBBackend):
    """PostgreSQL 后端 — psycopg2 连接池"""

    def __init__(self, host='localhost', port=5432, database='ai_vuln',
                 user='postgres', password='', pool_min=2, pool_max=10):
        self._pool = None
        self._params = dict(host=host, port=port, database=database,
                            user=user, password=password,
                            minconn=pool_min, maxconn=pool_max)

    def _ensure_pool(self):
        if self._pool is not None:
            return
        try:
            from psycopg2.pool import ThreadedConnectionPool
            self._pool = ThreadedConnectionPool(**self._params)
            logger.info("PostgreSQL 连接池已创建")
        except ImportError:
            raise RuntimeError("psycopg2 未安装: pip install psycopg2-binary")
        except Exception as e:
            logger.error(f"PG 连接失败: {e}")
            raise

    def connect(self, db_name: str = '') -> Any:
        self._ensure_pool()
        return self._pool.getconn()

    def placeholder(self) -> str:
        return '%s'

    def release(self, conn):
        if self._pool:
            self._pool.putconn(conn)

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None


# ============================================================
_backend_instance: Optional[DBBackend] = None


def create_backend(config=None) -> DBBackend:
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance
    if config is None:
        import config as cfg
    else:
        cfg = config
    if cfg.DB_BACKEND == 'postgresql':
        _backend_instance = PostgresBackend(
            host=cfg.PG_HOST, port=cfg.PG_PORT, database=cfg.PG_DATABASE,
            user=cfg.PG_USER, password=cfg.PG_PASSWORD,
            pool_min=cfg.PG_POOL_MIN, pool_max=cfg.PG_POOL_MAX)
    else:
        _backend_instance = SQLiteBackend(base_dir=cfg.DB_SQLITE_DIR)
    logger.info(f"后端: {type(_backend_instance).__name__}")
    return _backend_instance


def reset_backend():
    global _backend_instance
    if _backend_instance:
        _backend_instance.close()
    _backend_instance = None
