# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 扫描任务调度器

进程内调度器：优先队列（heapq）+ 后台轮询线程。支持一次性定时(run_at)
与周期任务(interval_seconds)。无第三方依赖；如需 APScheduler 可后续替换。
"""
import heapq
import itertools
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 优先级权重（数值越小越优先）
PRIORITY_WEIGHT = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}


class ScheduledTask:
    """调度任务"""

    def __init__(self, task_id: str, target: str, priority: str = 'medium',
                 scan_type: str = 'quick', ports: Optional[str] = None,
                 run_at: Optional[datetime] = None,
                 interval_seconds: Optional[float] = None,
                 func: Optional[Callable] = None):
        self.task_id = task_id
        self.target = target
        self.priority = priority
        self.scan_type = scan_type
        self.ports = ports
        self.run_at = run_at
        self.interval_seconds = interval_seconds
        # 周期任务未指定首次执行时间时，立即执行（否则 due() 因 run_at=None 永不触发）
        if interval_seconds is not None and run_at is None:
            self.run_at = datetime.now()
        self.func = func
        self.cancelled = False

    def due(self, now: datetime) -> bool:
        if self.cancelled or self.run_at is None:
            return False
        # run_at 可能带时区（外部 ISO 串），now 为本地 naive，统一为 naive 后比较，
        # 避免 naive >= aware 抛 TypeError
        run_at = self.run_at
        if run_at.tzinfo is not None:
            run_at = run_at.astimezone().replace(tzinfo=None)
        return now >= run_at


class ScanScheduler:
    """扫描任务调度器：优先队列 + 后台轮询线程"""

    def __init__(self):
        self._heap: List = []          # [(priority_weight, seq, task)]
        self._counter = itertools.count()
        self._tasks: Dict[str, ScheduledTask] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def add_task(self, task: ScheduledTask):
        weight = PRIORITY_WEIGHT.get(task.priority, 2)
        with self._lock:
            self._tasks[task.task_id] = task
            heapq.heappush(self._heap, (weight, next(self._counter), task))

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return False
            t.cancelled = True
            # 从堆与任务表中移除已取消任务
            self._heap = [(w, s, x) for w, s, x in self._heap if x is not t]
            heapq.heapify(self._heap)
            if self._tasks.get(task_id) is t:
                self._tasks.pop(task_id, None)
            return True

    def get_queue(self) -> List[Dict]:
        with self._lock:
            items = sorted((e for e in self._heap if not e[2].cancelled), key=lambda x: x[0])
            return [{'task_id': t.task_id, 'target': t.target, 'priority': t.priority,
                     'run_at': t.run_at.isoformat() if t.run_at else None,
                     'interval_seconds': t.interval_seconds} for _, _, t in items]

    def run_once_now(self, task_id: str):
        t = self._tasks.get(task_id)
        if t and t.func and not t.cancelled:
            t.func(t)

    def _poll(self):
        while self._running:
            try:
                self._poll_once()
            except Exception as e:
                # 单次轮询异常不应终止调度线程（否则所有后续任务静默失效）
                logger.error(f'调度轮询异常: {e}')
                time.sleep(1)

    def _poll_once(self):
        now = datetime.now()
        with self._lock:
            due = [t for _, _, t in self._heap if t.due(now)]
            for t in due:
                t.cancelled = True  # 防重复调度
                if t.interval_seconds:
                    t.run_at = now + timedelta(seconds=t.interval_seconds)
                    t.cancelled = False
        for t in due:
            try:
                if t.func:
                    t.func(t)
            except Exception as e:
                logger.error(f'调度任务执行失败 {t.task_id}: {e}')
        # 清理已消费的一次性任务，防止堆与任务表无限增长
        with self._lock:
            consumed = [t for _, _, t in self._heap if t.cancelled and not t.interval_seconds]
            for t in consumed:
                if self._tasks.get(t.task_id) is t:
                    self._tasks.pop(t.task_id, None)
            self._heap = [(w, s, t) for w, s, t in self._heap
                          if not (t.cancelled and not t.interval_seconds)]
            heapq.heapify(self._heap)
        time.sleep(1)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
