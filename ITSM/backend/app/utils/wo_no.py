"""工单号生成：WO-YYYY-NNNN（按年递增）。"""
import threading
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import WorkOrder

# PostgreSQL 咨询锁编号（任意固定值，用于串行化取号）
_WO_NO_LOCK_ID = 7471

# 非 PostgreSQL（SQLite 等，仅开发/测试用）在单进程内以线程锁串行化取号，
# 避免并发请求读到同一 max(no) 后撞唯一约束。生产走 PG 咨询锁（跨进程安全）。
_non_pg_lock = threading.Lock()


def _next(db: Session) -> str:
    year = datetime.now().year
    prefix = f"WO-{year}-"
    last = (
        db.query(WorkOrder.no)
        .filter(WorkOrder.no.like(f"{prefix}%"))
        .order_by(WorkOrder.no.desc())
        .first()
    )
    seq = int(last[0].split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def next_work_order_no(db: Session) -> str:
    if db.get_bind().dialect.name == "postgresql":
        # 事务级咨询锁：并发取号时串行化（跨进程安全），避免撞唯一约束
        db.execute(text(f"SELECT pg_advisory_xact_lock({_WO_NO_LOCK_ID})"))
        return _next(db)
    with _non_pg_lock:
        return _next(db)
