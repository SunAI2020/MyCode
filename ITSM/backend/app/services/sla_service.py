"""SLA 分级预警与升级链。"""
from datetime import date

from sqlalchemy.orm import Session

from app.models import ServiceCycle, ServiceReminder


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
