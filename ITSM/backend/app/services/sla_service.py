"""SLA 分级预警与升级链。"""
import re
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ContractItem,
    Escalation,
    ServiceCycle,
    ServiceReminder,
    SlaPolicy,
    WorkCalendar,
    WorkOrder,
)
from app.services.calendar_service import add_work_minutes, parse_time
from app.services.notify_service import notify_all_channels


def sla_level(service_end: date, today: date) -> str | None:
    """距工期结束 ≤1/3/7 天 → 红/橙/黄；超时红。"""
    days = (service_end - today).days
    if days < 0 or days <= 1:
        return "红"
    if days <= 3:
        return "橙"
    if days <= 7:
        return "黄"
    return None


def scan_sla_alerts(db: Session, today: date | None = None) -> int:
    """扫描未完成工期，生成分级预警提醒（同工期同级别去重）。返回新增数。"""
    today = today or date.today()
    cycles = db.query(ServiceCycle).filter(ServiceCycle.status.notin_(["done", "cancelled"])).all()
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
        content = f"服务工期将于 {c.service_end} 结束，SLA {level} 级预警"
        db.add(
            ServiceReminder(
                cycle_id=c.id,
                type="预警",
                level=level,
                content=content,
            )
        )
        notify_all_channels(content)  # 多渠道路由（未配置 webhook 时静默降级）
        created += 1
    db.commit()
    return created


def parse_resolve_limit(limit: str | None) -> int:
    """解析解决时限（"4小时"/"30分钟"/"2天"）为分钟；无法解析返回 0。"""
    if not limit:
        return 0
    m = re.match(r"(\d+)\s*(分钟|小时|天|min|hour|day|h|d)", limit)
    if not m:
        return 0
    n = int(m.group(1))
    unit = m.group(2)
    if unit in ("分钟", "min"):
        return n
    if unit in ("小时", "hour", "h"):
        return n * 60
    if unit in ("天", "day", "d"):
        return n * 1440
    return 0


def compute_sla_deadline(db: Session, contract_item_id: int, start: datetime) -> datetime | None:
    """按合同子项 SLA 策略（含工作日历）计算解决时限；无策略/时限返回 None。"""
    item = db.get(ContractItem, contract_item_id)
    if item is None or item.sla_policy_id is None:
        return None
    policy = db.get(SlaPolicy, item.sla_policy_id)
    if policy is None:
        return None
    minutes = parse_resolve_limit(policy.resolve_limit)
    if minutes <= 0:
        return None
    if policy.work_calendar_id is not None:
        cal = db.get(WorkCalendar, policy.work_calendar_id)
        if cal is not None:
            days = {int(x) for x in cal.work_days.split(",") if x.strip()}
            return add_work_minutes(start, minutes, days, parse_time(cal.work_start), parse_time(cal.work_end))
    return start + timedelta(minutes=minutes)


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
            WorkOrder.status.notin_(["已结单", "已取消", "已关闭"]),
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
