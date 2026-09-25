"""周期拆分与生成（幂等）。"""
import calendar
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Contract, ContractItem, ServiceCycle

# 单位别名：中文（前端/模型实际存储）与英文（种子字典 code）统一映射
UNIT_ALIASES = {
    "天": "day", "day": "day",
    "周": "week", "week": "week",
    "月": "month", "month": "month",
    "季度": "quarter", "quarter": "quarter",
    "半年": "half_year", "half_year": "half_year",
    "年": "year", "year": "year",
    "不定期": "irregular", "irregular": "irregular",
}

IRREGULAR = "irregular"


def normalize_unit(unit: str) -> str:
    return UNIT_ALIASES.get(unit, unit)


def _add_months(d: date, months: int) -> date:
    idx = d.year * 12 + d.month - 1 + months
    y, m = divmod(idx, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _unit_end(d: date, unit: str) -> date:
    if unit == "day":
        return d + timedelta(days=1)
    if unit == "week":
        return d + timedelta(days=7)
    if unit == "month":
        return _add_months(d, 1)
    if unit == "quarter":
        return _add_months(d, 3)
    if unit == "half_year":
        return _add_months(d, 6)
    if unit == "year":
        return _add_months(d, 12)
    raise ValueError(f"未知周期单位：{unit}")


def split_cycles(start: date, end: date, frequency: int, unit: str) -> list[tuple[int, date, date]]:
    """把 [start, end) 按 unit 分段、每段按 frequency 等分，返回 (cycle_no, start, end)。

    边界去重且严格递增，避免零长/重叠周期（如 day + frequency>1 时退化为 1 个周期）。
    """
    unit = normalize_unit(unit)
    if unit == IRREGULAR or frequency <= 0 or end <= start:
        return []
    cycles: list[tuple[int, date, date]] = []
    cursor = start
    no = 0
    while cursor < end:
        u_end = min(_unit_end(cursor, unit), end)
        span = (u_end - cursor).days
        if span <= 0:
            break
        boundaries: list[date] = []
        for i in range(frequency + 1):
            b = cursor + timedelta(days=int(round(span * i / frequency)))
            if not boundaries or b > boundaries[-1]:
                boundaries.append(b)
        for i in range(len(boundaries) - 1):
            s, e = boundaries[i], boundaries[i + 1]
            if e <= s:
                continue
            no += 1
            cycles.append((no, s, e))
        cursor = u_end
    return cycles


def generate_cycles(db: Session, item_id: int) -> dict:
    """为合同子项生成服务周期（幂等）。返回 {"total": 应生成数, "created": 本次新增数}。"""
    item = db.get(ContractItem, item_id)
    if item is None:
        raise ValueError("子项不存在")
    contract = db.get(Contract, item.contract_id)
    if contract is None or contract.start_date is None or contract.end_date is None:
        raise ValueError("合同缺少起止日期")
    cycles = split_cycles(contract.start_date, contract.end_date, item.frequency, item.unit)
    created = 0
    for no, s, e in cycles:
        if db.query(ServiceCycle).filter_by(contract_item_id=item_id, cycle_no=no).first():
            continue
        db.add(
            ServiceCycle(
                contract_item_id=item_id,
                cycle_no=no,
                service_start=s,
                service_end=e,
                status="pending",
                auto_generated=True,
            )
        )
        created += 1
    db.commit()
    return {"total": len(cycles), "created": created}
