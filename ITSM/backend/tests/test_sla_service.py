"""SLA 分级预警单测。"""
from datetime import date

from app.services.sla_service import sla_level


def test_sla_levels():
    end = date(2024, 12, 31)
    assert sla_level(end, date(2024, 12, 30)) == "红"   # 距 1 天
    assert sla_level(end, date(2024, 12, 28)) == "橙"   # 距 3 天
    assert sla_level(end, date(2024, 12, 24)) == "黄"   # 距 7 天
    assert sla_level(end, date(2024, 12, 20)) is None   # 距 11 天
    assert sla_level(end, date(2025, 1, 2)) == "红"     # 超时
