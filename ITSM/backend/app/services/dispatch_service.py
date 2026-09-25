"""派单 / 换岗分摊。"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import WorkOrderAssignee


def transfer_assignee(
    db: Session,
    work_order_id: int,
    from_user_id: int,
    to_user_id: int,
    actual_hours: float | None = None,
) -> WorkOrderAssignee:
    """换岗：旧执行人离岗（记 actual_hours/ended_at），新执行人续接（继承原比例）。"""
    if from_user_id == to_user_id:
        raise ValueError("原执行人与新执行人不能为同一人")
    old = (
        db.query(WorkOrderAssignee)
        .filter_by(work_order_id=work_order_id, user_id=from_user_id, is_active=True)
        .first()
    )
    if old is None:
        raise ValueError("原执行人不存在或已离岗")
    dup = (
        db.query(WorkOrderAssignee)
        .filter_by(work_order_id=work_order_id, user_id=to_user_id, is_active=True)
        .first()
    )
    if dup is not None:
        raise ValueError("新执行人已在本工单执行中")
    now = datetime.now(timezone.utc)
    old.is_active = False
    old.ended_at = now
    if actual_hours is not None:
        old.actual_hours = actual_hours
    new = WorkOrderAssignee(
        work_order_id=work_order_id,
        user_id=to_user_id,
        workload_ratio=old.workload_ratio,
        started_at=now,
        is_active=True,
    )
    db.add(new)
    db.flush()
    return new
