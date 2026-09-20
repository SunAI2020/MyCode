"""
7×24 定时调度器（自包含，守护线程 + 每秒 tick）。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskScheduler:
    """周期任务调度器：add_job 注册任务，start/stop 控制循环，run_once 供测试/手动触发。"""

    def __init__(self):
        self._jobs: List[Dict] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def add_job(self, name: str, interval_seconds: float, func: Callable[[], None]) -> None:
        self._jobs.append({"name": name, "interval": interval_seconds, "func": func})

    def run_once(self) -> None:
        """同步执行一轮所有 job（异常隔离，不中断其它 job）。"""
        for j in self._jobs:
            try:
                j["func"]()
            except Exception as e:  # noqa: BLE001
                logger.warning("调度任务 %s 失败: %s", j["name"], e)

    def start(self) -> None:
        """启动守护线程循环（每秒 tick）。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pts-scheduler")
        self._thread.start()

    def _loop(self) -> None:
        next_run: Dict[str, float] = {}
        while not self._stop_event.is_set():
            now = time.time()
            for j in self._jobs:
                if now >= next_run.get(j["name"], 0.0):
                    try:
                        j["func"]()
                    except Exception as e:  # noqa: BLE001
                        logger.warning("调度任务 %s 失败: %s", j["name"], e)
                    next_run[j["name"]] = now + j["interval"]
            self._stop_event.wait(1.0)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
