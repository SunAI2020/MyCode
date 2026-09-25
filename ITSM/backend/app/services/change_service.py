"""变更单业务逻辑：冲突检测 + 状态机。"""
from sqlalchemy.orm import Session

from app.models import ChangeOrder

# 视为「活跃」、参与冲突检测的状态
ACTIVE_STATUSES = {"待审批", "已批准", "实施中"}

TRANSITIONS = {
    "草稿": ["待审批", "已取消"],
    "待审批": ["已批准", "已拒绝"],
    "已批准": ["实施中", "已取消"],
    "实施中": ["已完成", "已回滚"],
    "已完成": [],
    "已回滚": [],
    "已拒绝": [],
    "已取消": [],
}


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


def transition_status(db: Session, change: ChangeOrder, target: str) -> ChangeOrder:
    """校验并执行变更状态流转。"""
    allowed = TRANSITIONS.get(change.status, [])
    if target == change.status:
        return change
    if target not in allowed:
        raise ValueError(f"非法状态流转：{change.status} → {target}")
    change.status = target
    db.flush()
    return change
