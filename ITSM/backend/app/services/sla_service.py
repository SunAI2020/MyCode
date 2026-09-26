"""SLA 分级预警与升级链。"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ContractItem,
    Escalation,
    ServiceCycle,
    ServiceReminder,
    SlaPolicy,
    WorkOrder,
)


def sla_level(service_end: date, today: date) -> str | None:
    """距周期结束 ≤1/3/7 天 → 红/橙/黄；超时红。"""
    days = (service_end - today).days
    if days < 0 or days <= 1:
        return "红"
    if days <= 3:
        return "橙"
    if days <= 7:
        return "黄"
    return None


def scan_sla_alerts(db: Session, today: date | None = None) -> int:
    """扫描未完成周期，生成分级预警提醒（同周期同级别去重）。返回新增数。"""
    today = today or date.today()
    cycles = db.query(ServiceCycle).filter(ServiceCycle.status != "done").all()
    created = 0
    for c in cycles:
        level = sla_level(c.service_end, today)
        if level is None:
            continue
        dup = (
            db.query(ServiceReminder)
            .filter_by(cycle_id=c.id, type="预警", level=level)
            .first()
        )
        if dup:
            continue
        db.add(
            ServiceReminder(
                cycle_id=c.id,
                type="预警",
                level=level,
                content=f"服务周期将于 {c.service_end} 结束，SLA {level} 级预警",
            )
        )
        created += 1
    db.commit()
    return created


def _escalation_chain_of(db: Session, wo: WorkOrder) -> list[str] | None:
    """解析工单的升级链（执行人→经理→负责人）；无法解析返回 None。"""
    if wo.contract_item_id is None:
        return None
    item = db.get(ContractItem, wo.contract_item_id)
    if item is None or item.sla_policy_id is None:
        return None
    policy = db.get(SlaPolicy, item.sla_policy_id)
    if policy is None or not policy.escalation_chain:
        return None
    nodes = [n.strip() for n in policy.escalation_chain.split("→") if n.strip()]
    return nodes if len(nodes) >= 2 else None


def scan_sla_escalations(db: Session, today: date | None = None) -> int:
    """扫描 SLA 超时未完工单，按升级链首级生成升级记录（同工单同级别去重）。"""
    today = today or date.today()
    wos = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.sla_deadline.isnot(None),
            func.date(WorkOrder.sla_deadline) < today,
            WorkOrder.status.notin_(["已完成", "已关闭", "已取消"]),
        )
        .all()
    )
    created = 0
    for wo in wos:
        nodes = _escalation_chain_of(db, wo)
        if nodes is None:
            continue
        from_u, to_u = nodes[0], nodes[1]
        dup = (
            db.query(Escalation)
            .filter_by(work_order_id=wo.id, level="红", from_user=from_u, to_user=to_u)
            .first()
        )
        if dup:
            continue
        db.add(
            Escalation(
                work_order_id=wo.id,
                level="红",
                from_user=from_u,
                to_user=to_u,
                reason=f"工单 {wo.no} SLA 超时，升级至 {to_u}",
            )
        )
        created += 1
    db.commit()
    return created
