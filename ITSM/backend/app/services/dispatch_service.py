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
    """换岗：旧执行人离岗（记 actual_hours/ended_at），新执行人续接（继承原比例）。

    旧执行人保留原 workload_ratio 作为其历史分摊比例（绩效按 actual_hours×ratio 精确
    归属），新执行人以同一比例续接同一工作切片、后续另记自己的 actual_hours。
    """
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


def record_assignee_hours(
    db: Session,
    work_order_id: int,
    user_id: int,
    actual_hours: float,
    complete: bool = False,
) -> WorkOrderAssignee:
    """记录执行人实际工时（换岗后新执行人续接完成后回填），可选离岗。

    换岗后绩效精确归属依赖各执行人（含新旧）都记有 actual_hours；本函数补上新执行人
    的工时入口，避免 generate_performance 因 actual_hours 为空而给 0 分。
    """
    a = (
        db.query(WorkOrderAssignee)
        .filter_by(work_order_id=work_order_id, user_id=user_id, is_active=True)
        .first()
    )
    if a is None:
        raise ValueError("执行人不存在或已离岗")
    a.actual_hours = actual_hours
    if complete:
        a.is_active = False
        a.ended_at = datetime.now(timezone.utc)
    db.flush()
    return a
