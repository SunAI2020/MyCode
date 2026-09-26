"""周期拆分算法单测（对应 §9.2：2次/周跨月均匀、无重复遗漏）。"""
from datetime import date

from app.models import Contract, ContractItem, Customer, ServiceCycle
from app.services.cycle_service import generate_cycles, split_cycles


def test_two_per_week_cross_month():
    # 2024-02-26(周一) ~ 2024-03-04(周一)，正好 7 天跨 2/3 月边界
    cycles = split_cycles(date(2024, 2, 26), date(2024, 3, 4), 2, "week")
    # 1 个周段 × 2 次 = 2 个周期
    assert len(cycles) == 2
    nos = [c[0] for c in cycles]
    assert nos == [1, 2]  # 无重复、无遗漏
    # 时间连续覆盖整周：首周期起点 == start，末周期终点 == end
    assert cycles[0][1] == date(2024, 2, 26)
    assert cycles[-1][2] == date(2024, 3, 4)
    # 相邻周期首尾相接（无空洞）
    assert cycles[0][2] == cycles[1][1]


def test_quarterly_once_per_year():
    cycles = split_cycles(date(2024, 1, 1), date(2025, 1, 1), 1, "quarter")
    assert len(cycles) == 4  # 一年 4 季度
    assert [c[0] for c in cycles] == [1, 2, 3, 4]


def test_daily():
    cycles = split_cycles(date(2024, 1, 1), date(2024, 1, 4), 1, "day")
    assert len(cycles) == 3


def test_irregular_returns_empty():
    assert split_cycles(date(2024, 1, 1), date(2024, 12, 31), 1, "不定期") == []
    assert split_cycles(date(2024, 1, 1), date(2024, 12, 31), 1, "irregular") == []


def test_invalid_input_returns_empty():
    assert split_cycles(date(2024, 1, 1), date(2024, 1, 1), 1, "month") == []
    assert split_cycles(date(2024, 2, 1), date(2024, 1, 1), 1, "month") == []
    assert split_cycles(date(2024, 1, 1), date(2024, 2, 1), 0, "month") == []


def test_chinese_unit_alias():
    # 中文单位（前端/模型实际存储）与英文等价
    zh = split_cycles(date(2024, 1, 1), date(2024, 4, 1), 1, "月")
    en = split_cycles(date(2024, 1, 1), date(2024, 4, 1), 1, "month")
    assert len(zh) == len(en) == 3
    assert [c[0] for c in zh] == [c[0] for c in en]


def test_day_high_frequency_no_duplicate():
    # day + frequency>1 应退化为 1 个周期，不产生重复/零长周期
    cycles = split_cycles(date(2024, 1, 1), date(2024, 1, 2), 3, "day")
    assert len(cycles) == 1
    assert cycles[0][1] == date(2024, 1, 1)
    assert cycles[0][2] == date(2024, 1, 2)


def test_generate_cycles_rebuild_on_frequency_change(db):
    c = Customer(name="A")
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name="x", start_date=date(2024, 1, 1), end_date=date(2025, 1, 1))
    db.add(ct)
    db.flush()
    item = ContractItem(contract_id=ct.id, project="OA", frequency=1, unit="月")
    db.add(item)
    db.commit()

    generate_cycles(db, item.id)
    assert db.query(ServiceCycle).filter_by(contract_item_id=item.id).count() == 12

    item.frequency = 2  # 改为每月 2 次
    db.commit()
    generate_cycles(db, item.id)
    rows = db.query(ServiceCycle).filter_by(contract_item_id=item.id).order_by(ServiceCycle.cycle_no).all()
    # 旧 12 个 pending 周期被清除，按新频率重建为 24 个，无旧日期残留
    assert len(rows) == 24
    assert [r.cycle_no for r in rows] == list(range(1, 25))
    # 全部为 pending（重建），无 started/done 遗留
    assert all(r.status == "pending" for r in rows)
