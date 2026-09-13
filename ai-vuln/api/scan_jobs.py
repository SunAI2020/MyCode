# -*- coding: utf-8 -*-
"""异步扫描任务管理 — 进程内任务注册表（供轮询端点查询）"""
import threading
import time
import uuid
from typing import Dict, Optional

_jobs: Dict[str, Dict] = {}
_lock = threading.Lock()

# 任务保留时长（秒），超时自动清理，防止内存泄漏
_JOB_TTL = 3600


def create_job() -> str:
    """创建任务，返回 job_id"""
    job_id = uuid.uuid4().hex
    now = time.time()
    with _lock:
        _jobs[job_id] = {
            'job_id': job_id,
            'status': 'pending',  # pending | running | completed | failed
            'result': None,
            'error': None,
            'created_at': now,
        }
        # 顺带清理过期任务
        expired = [jid for jid, j in _jobs.items() if now - j['created_at'] > _JOB_TTL]
        for jid in expired:
            del _jobs[jid]
    return job_id


def update_job(job_id: str, status: str, result=None, error=None) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job['status'] = status
        if result is not None:
            job['result'] = result
        if error is not None:
            job['error'] = error


def get_job(job_id: str) -> Optional[Dict]:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job is not None else None
