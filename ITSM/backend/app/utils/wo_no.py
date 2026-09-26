"""工单号生成：WO-YYYY-NNNN（按年递增）。"""
import threading
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import WorkOrder

# PostgreSQL 咨询锁编号（任意固定值，用于串行化取号）
_WO_NO_LOCK_ID = 7471

# 非 PostgreSQL（SQLite 等，仅开发/测试用）在单进程内以线程锁串行化取号。
# 锁必须跨越「取号 + 插入 + commit」，否则并发请求会读到同一 max(no) 后撞唯一约束。
_non_pg_lock = threading.Lock()


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


@contextmanager
def work_order_no_scope(db: Session):
    """取号临界区：须覆盖「取号 + 插入 + commit」，防止并发撞唯一约束。

    - PostgreSQL：事务级咨询锁（跨进程安全，随事务提交/回滚自动释放）。
    - 非 PostgreSQL：进程内线程锁（开发/测试单进程）。
    调用方须在 `with work_order_no_scope(db):` 块内完成取号、add 与 commit。
    """
    if _is_postgres(db):
        db.execute(text(f"SELECT pg_advisory_xact_lock({_WO_NO_LOCK_ID})"))
        yield
    else:
        with _non_pg_lock:
            yield


def next_work_order_no(db: Session) -> str:
    """生成下一个工单号（应在 work_order_no_scope 临界区内调用）。"""
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
