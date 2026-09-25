"""可配置工作流引擎：状态流转规则（DB 覆盖/扩展内置默认）+ 全量动作留痕。

- 内置 `DEFAULT_TRANSITIONS` 兜底（开箱即用，与既有业务逐字节一致）；
- `workflow_rule`（enabled）新增/扩展自定义流转边，与默认取并集；
- 每次成功流转写 `action_log` 全量留痕（实体/主键/前后态/操作人/备注）。
"""
from sqlalchemy.orm import Session

from app.models import ActionLog, WorkflowRule

# 内置默认状态机（按实体）。DB 规则可与默认取并集，因此默认不可被「禁止」，
# 仅能被「扩展」——如需收缩某条边，由业务端点自行加判断（不在本引擎职责内）。
DEFAULT_TRANSITIONS: dict[str, dict[str, list[str]]] = {
    "work_order": {
        "待派单": ["已派单", "已取消"],
        "已派单": ["计划中", "已取消"],
        "计划中": ["进行中", "已取消"],
        "进行中": ["待验收", "已关闭"],
        "待验收": ["已完成", "已关闭"],
        "已完成": ["已关闭"],
        "已关闭": [],
        "已取消": [],
    },
    "change_order": {
        "草稿": ["待审批", "已取消"],
        "待审批": ["已批准", "已拒绝"],
        "已批准": ["实施中", "已取消"],
        "实施中": ["已完成", "已回滚"],
        "已完成": [],
        "已回滚": [],
        "已拒绝": [],
        "已取消": [],
    },
    "outsourcing": {
        "待接单": ["已接单", "已拒单"],
        "已接单": ["进行中", "已拒单"],
        "进行中": ["待验收"],
        "待验收": ["已验收", "进行中"],
        "已验收": ["已结算"],
        "已结算": [],
        "已拒单": [],
    },
}


def allowed_targets(db: Session, entity: str, from_status: str) -> list[str]:
    """返回实体在 from_status 下的合法目标态 = 默认 ∪ DB（去重、保序）。"""
    targets: list[str] = list(DEFAULT_TRANSITIONS.get(entity, {}).get(from_status, []))
    rows = (
        db.query(WorkflowRule)
        .filter_by(entity=entity, from_status=from_status, enabled=True)
        .all()
    )
    for r in rows:
        if r.to_status not in targets:
            targets.append(r.to_status)
    return targets


def can_transition(db: Session, entity: str, from_status: str, target: str) -> bool:
    """是否允许 from_status → target（同态视为合法）。"""
    return target == from_status or target in allowed_targets(db, entity, from_status)


def assert_transition(db: Session, entity: str, from_status: str, target: str) -> None:
    """校验状态流转；非法则抛 ValueError。"""
    if not can_transition(db, entity, from_status, target):
        raise ValueError(f"非法状态流转：{from_status} → {target}")


def log_transition(
    db: Session,
    *,
    entity: str,
    entity_id: int,
    from_status: str,
    to_status: str,
    operator_id: int | None = None,
    note: str | None = None,
) -> ActionLog:
    """记录一次状态流转（全量留痕），返回日志对象（未 flush）。"""
    log = ActionLog(
        entity=entity,
        entity_id=entity_id,
        from_status=from_status,
        to_status=to_status,
        operator_id=operator_id,
        note=note,
    )
    db.add(log)
    return log
