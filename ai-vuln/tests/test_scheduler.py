# -*- coding: utf-8 -*-
"""扫描任务调度器测试"""
from datetime import datetime, timedelta
from scheduler import ScanScheduler, ScheduledTask


def test_priority_queue_order():
    s = ScanScheduler()
    s.add_task(ScheduledTask('low', 't1', priority='low'))
    s.add_task(ScheduledTask('high', 't2', priority='high'))
    s.add_task(ScheduledTask('critical', 't3', priority='critical'))
    q = s.get_queue()
    assert [x['task_id'] for x in q] == ['critical', 'high', 'low']


def test_cancel():
    s = ScanScheduler()
    s.add_task(ScheduledTask('a', 't1'))
    assert s.cancel('a') is True
    assert s.cancel('missing') is False


def test_due_logic():
    now = datetime.now()
    past = ScheduledTask('a', 't1', run_at=now - timedelta(seconds=5))
    future = ScheduledTask('b', 't2', run_at=now + timedelta(seconds=60))
    assert past.due(now) is True
    assert future.due(now) is False


def test_cancelled_not_due():
    t = ScheduledTask('a', 't1', run_at=datetime.now() - timedelta(seconds=5))
    t.cancelled = True
    assert t.due(datetime.now()) is False


def test_run_once_now_invokes_func():
    s = ScanScheduler()
    calls = []
    t = ScheduledTask('a', 't1', func=lambda task: calls.append(task.task_id))
    s.add_task(t)
    s.run_once_now('a')
    assert calls == ['a']


def test_cancel_removes_from_queue():
    s = ScanScheduler()
    s.add_task(ScheduledTask('a', 't1'))
    s.add_task(ScheduledTask('b', 't2'))
    s.cancel('a')
    q = s.get_queue()
    assert [x['task_id'] for x in q] == ['b']


def test_run_once_now_skips_cancelled():
    s = ScanScheduler()
    calls = []
    t = ScheduledTask('a', 't1', func=lambda task: calls.append(task.task_id))
    s.add_task(t)
    s.cancel('a')
    s.run_once_now('a')
    assert calls == []
