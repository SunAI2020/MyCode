"""工单号生成：WO-YYYY-NNNN（按年递增）。"""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import WorkOrder

# PostgreSQL 咨询锁编号（任意固定值，用于串行化取号）
_WO_NO_LOCK_ID = 7471


def next_work_order_no(db: Session) -> str:
    # 事务级咨询锁：并发取号时串行化，避免撞唯一约束（SQLite 自动跳过）
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(f"SELECT pg_advisory_xact_lock({_WO_NO_LOCK_ID})"))
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
