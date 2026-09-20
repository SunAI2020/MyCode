"""
定时任务持久化（SQLite）。

自包含：任务存 data/scheduled_tasks.db，字段 id/name/target/interval_minutes/enabled。
供 GUI 的 TaskScheduler 加载（list_enabled）与 ScheduledTaskDialog 管理（增删改）。
本模块不 import 任何 core 模块，可被 GUI 安全单向引用。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "scheduled_tasks.db"


class TaskStore:
    """SQLite 定时任务存储。"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or _DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS scheduled_tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "name TEXT NOT NULL,"
                "target TEXT NOT NULL,"
                "interval_minutes INTEGER NOT NULL,"
                "enabled INTEGER NOT NULL DEFAULT 1)"
            )

    def list(self) -> List[Dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, name, target, interval_minutes, enabled "
                "FROM scheduled_tasks ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def list_enabled(self) -> List[Dict]:
        return [t for t in self.list() if t["enabled"]]

    def add(self, name: str, target: str, interval_minutes: int,
            enabled: bool = True) -> int:
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO scheduled_tasks (name, target, interval_minutes, enabled) "
                "VALUES (?, ?, ?, ?)",
                (name, target, interval_minutes, 1 if enabled else 0))
            return cur.lastrowid

    def update(self, task_id: int, name: str, target: str,
               interval_minutes: int, enabled: bool) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE scheduled_tasks SET name=?, target=?, interval_minutes=?, enabled=? "
                "WHERE id=?",
                (name, target, interval_minutes, 1 if enabled else 0, task_id))

    def delete(self, task_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM scheduled_tasks WHERE id=?", (task_id,))
