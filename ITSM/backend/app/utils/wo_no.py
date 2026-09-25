"""工单号生成：WO-YYYY-NNNN（按年递增）。"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import WorkOrder


def next_work_order_no(db: Session) -> str:
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
