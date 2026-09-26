"""工作日历单测：add_work_minutes 跳过非工作时段。"""
from datetime import datetime, timedelta, time

from app.services.calendar_service import add_work_minutes

DAYS = {1, 2, 3, 4, 5}
WS = time(9, 0)
WE = time(18, 0)


def test_add_within_day():
    start = datetime(2026, 9, 21, 9, 0)  # 周一 09:00
    assert add_work_minutes(start, 60, DAYS, WS, WE) == datetime(2026, 9, 21, 10, 0)


def test_add_cross_day_end():
    start = datetime(2026, 9, 21, 17, 30)  # 周一 17:30，18:00 下班
    # 当天剩 30 分钟 + 周二 30 分钟 = 周二 09:30
    assert add_work_minutes(start, 60, DAYS, WS, WE) == datetime(2026, 9, 22, 9, 30)


def test_add_skip_weekend():
    start = datetime(2026, 9, 25, 17, 0)  # 周五 17:00
    # 周五剩 60 分钟 + 周一 60 分钟 = 周一 10:00
    assert add_work_minutes(start, 120, DAYS, WS, WE) == datetime(2026, 9, 28, 10, 0)


def test_add_skip_before_work_start():
    start = datetime(2026, 9, 21, 8, 0)  # 周一 08:00（上班前）
    assert add_work_minutes(start, 30, DAYS, WS, WE) == datetime(2026, 9, 21, 9, 30)


def test_add_empty_work_days():
    # 空工作日集合按自然时间兜底，不进入死循环
    start = datetime(2026, 9, 21, 9, 0)
    assert add_work_minutes(start, 60, set(), WS, WE) == start + timedelta(minutes=60)
