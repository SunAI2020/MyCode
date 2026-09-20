"""
core.scheduler 测试：TaskScheduler。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scheduler import TaskScheduler


def test_run_once_triggers_jobs():
    calls = []
    s = TaskScheduler()
    s.add_job("a", 60, lambda: calls.append("a"))
    s.add_job("b", 60, lambda: calls.append("b"))
    s.run_once()
    assert calls == ["a", "b"]


def test_run_once_isolates_exception():
    calls = []

    def boom():
        raise RuntimeError("boom")

    s = TaskScheduler()
    s.add_job("boom", 60, boom)
    s.add_job("ok", 60, lambda: calls.append("ok"))
    s.run_once()  # 不抛异常，异常隔离
    assert calls == ["ok"]


def test_stop_without_start_is_safe():
    s = TaskScheduler()
    s.stop()  # 未启动也安全
