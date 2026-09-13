# -*- coding: utf-8 -*-
"""API响应缓存 — SQLite LRU+TTL"""
import os, sys, sqlite3, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import CACHE_DB_PATH

class CacheManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or CACHE_DB_PATH
        self._init_db()
    def _connect(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row; return conn
    def _init_db(self):
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires_at TEXT, created_at TEXT)")
            conn.commit()
    def get(self, key):
        with self._connect() as conn:
            row = conn.execute("SELECT value,expires_at FROM cache WHERE key=? AND expires_at>?",
                (key, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))).fetchone()
        return json.loads(row["value"]) if row else None
    def set(self, key, value, ttl_seconds=3600):
        now = datetime.now()
        exp = now if ttl_seconds == 0 else datetime.fromtimestamp(now.timestamp()+ttl_seconds)
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)",
                (key, json.dumps(value,ensure_ascii=False,default=str),
                 exp.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    def clear_expired(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE expires_at<=?",(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
            conn.commit()
    def clear_all(self):
        with self._connect() as conn: conn.execute("DELETE FROM cache"); conn.commit()
