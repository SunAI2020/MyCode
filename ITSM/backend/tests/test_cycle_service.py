"""周期拆分算法单测（对应 §9.2：2次/周跨月均匀、无重复遗漏）。"""
from datetime import date

from app.services.cycle_service import split_cycles


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
