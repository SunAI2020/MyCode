"""工作日历工具：SLA 计时跳过非工作时段。"""
from datetime import datetime, time, timedelta


def parse_time(s: str) -> time:
    """解析 "HH:MM" 为 time。"""
    h, m = s.split(":")
    return time(int(h), int(m))


def add_work_minutes(
    start: datetime,
    minutes: int,
    work_days: set[int],
    work_start: time,
    work_end: time,
) -> datetime:
    """在 work_days 的工作时段内累加 minutes 分钟，跳过非工作日 / 非工作时段。"""
    if minutes <= 0:
        return start
    if not work_days:
        return start + timedelta(minutes=minutes)  # 无工作日定义 → 按自然时间兜底
    cur = start
    remaining = minutes
    while remaining > 0:
        if cur.weekday() + 1 not in work_days:
            # 非工作日 → 次日 0 点再定位
            cur = cur.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            continue
        ws = cur.replace(hour=work_start.hour, minute=work_start.minute, second=0, microsecond=0)
        we = cur.replace(hour=work_end.hour, minute=work_end.minute, second=0, microsecond=0)
        if cur < ws:
            cur = ws
        if cur >= we:
            cur = cur.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            continue
        available = int((we - cur).total_seconds() // 60)
        if available >= remaining:
            return cur + timedelta(minutes=remaining)
        remaining -= available
        cur = we
    return cur
