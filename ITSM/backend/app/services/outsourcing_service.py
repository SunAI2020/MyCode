"""外包协作业务逻辑：状态机。"""
from sqlalchemy.orm import Session

from app.models import Outsourcing

# 外包任务状态机（合法迁移表）
TRANSITIONS = {
    "待接单": ["已接单", "已拒单"],
    "已接单": ["进行中", "已拒单"],
    "进行中": ["待验收"],
    "待验收": ["已验收", "进行中"],  # 验收不通过回退整改
    "已验收": ["已结算"],
    "已结算": [],
    "已拒单": [],
}


def transition_status(db: Session, outsourcing: Outsourcing, target: str) -> Outsourcing:
    """校验并执行外包任务状态流转。"""
    allowed = TRANSITIONS.get(outsourcing.status, [])
    if target == outsourcing.status:
        return outsourcing
    if target not in allowed:
        raise ValueError(f"非法状态流转：{outsourcing.status} → {target}")
    outsourcing.status = target
    db.flush()
    return outsourcing
