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


def set_conflict_flag(db: Session, change: ChangeOrder, previous_ci_id: int | None = None) -> ChangeOrder:
    """按当前同一 CI 活跃变更重算冲突标记（对称：同 CI 其他活跃变更一并重算）。

    否则仅对传入变更打标记，既有活跃变更侧始终为 False，冲突列表漏报一半。
    previous_ci_id：变更单 ci_id 被修改前的旧值；旧 CI 上此前因本变更而置 True 的
    兄弟变更需一并重算，否则残留过期冲突标记。
    """
    change.conflict_flag = bool(detect_conflict(db, change.ci_id, change.id))
    siblings = (
        db.query(ChangeOrder)
        .filter(
            ChangeOrder.ci_id == change.ci_id,
            ChangeOrder.id != change.id,
            ChangeOrder.status.in_(ACTIVE_STATUSES),
        )
        .all()
    )
    for s in siblings:
        s.conflict_flag = bool(detect_conflict(db, s.ci_id, s.id))
    if previous_ci_id is not None and previous_ci_id != change.ci_id:
        old_siblings = (
            db.query(ChangeOrder)
            .filter(
                ChangeOrder.ci_id == previous_ci_id,
                ChangeOrder.id != change.id,
                ChangeOrder.status.in_(ACTIVE_STATUSES),
            )
            .all()
        )
        for s in old_siblings:
            s.conflict_flag = bool(detect_conflict(db, s.ci_id, s.id))
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
