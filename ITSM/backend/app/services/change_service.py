"""变更单业务逻辑：冲突检测 + 状态机（接入可配置工作流引擎）。"""
from sqlalchemy.orm import Session

from app.models import ChangeOrder
from app.services.workflow_service import assert_transition, log_transition

# 视为「活跃」、参与冲突检测的状态
ACTIVE_STATUSES = {"待审批", "已批准", "实施中"}


def detect_conflict(db: Session, ci_id: int, exclude_id: int | None = None) -> list[ChangeOrder]:
    """返回同一 CI 上其他活跃变更（冲突源）。"""
    q = db.query(ChangeOrder).filter(
        ChangeOrder.ci_id == ci_id,
        ChangeOrder.status.in_(ACTIVE_STATUSES),
    )
    if exclude_id is not None:
        q = q.filter(ChangeOrder.id != exclude_id)
    return q.all()


def set_conflict_flag(db: Session, change: ChangeOrder) -> ChangeOrder:
    """按当前同一 CI 活跃变更重算冲突标记。"""
    change.conflict_flag = bool(detect_conflict(db, change.ci_id, change.id))
    db.flush()
    return change


def transition_status(
    db: Session,
    change: ChangeOrder,
    target: str,
    operator_id: int | None = None,
    note: str | None = None,
) -> ChangeOrder:
    """校验并执行变更状态流转（接入可配置工作流引擎，全量留痕）。"""
    assert_transition(db, "change_order", change.status, target)
    if target == change.status:
        return change
    before = change.status
    change.status = target
    log_transition(
        db,
        entity="change_order",
        entity_id=change.id,
        from_status=before,
        to_status=target,
        operator_id=operator_id,
        note=note,
    )
    db.flush()
    return change
