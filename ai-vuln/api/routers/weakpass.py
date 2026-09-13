# -*- coding: utf-8 -*-
"""弱口令检测 API（异步任务 + 轮询）"""
from fastapi import APIRouter, Depends, BackgroundTasks

from api.dependencies import get_db, require_role
from api.models import WeakPassRequest, APIResponse
from api.scan_jobs import create_job, update_job, get_job
from weak_password_scanner import WeakPasswordScanner

router = APIRouter()


def _run_weakpass(job_id: str, body: WeakPassRequest, db):
    """后台执行弱口令检测"""
    try:
        update_job(job_id, 'running')
        scanner = WeakPasswordScanner(db=db)
        result = scanner.scan(body.host, body.port, body.protocol, credentials=body.credentials)
        update_job(job_id, 'completed', result=result)
    except Exception as e:
        update_job(job_id, 'failed', error=str(e))


@router.post('/weakpass/scan', response_model=APIResponse)
def run_weak_password_scan(body: WeakPassRequest, background: BackgroundTasks,
                           db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    """提交弱口令检测任务（异步），返回 job_id 供轮询"""
    job_id = create_job()
    background.add_task(_run_weakpass, job_id, body, db)
    return APIResponse(data={'job_id': job_id}, message='弱口令检测任务已提交')


@router.get('/weakpass/jobs/{job_id}', response_model=APIResponse)
def get_weakpass_job(job_id: str, _=Depends(require_role('admin', 'analyst'))):
    """轮询任务状态（与提交端点同角色门控，防 IDOR）"""
    job = get_job(job_id)
    if not job:
        return APIResponse(success=False, message='任务不存在或已过期')
    return APIResponse(data=job)


@router.get('/weakpass/dictionary', response_model=APIResponse)
def list_dictionary(protocol: str = None, db=Depends(get_db),
                    _=Depends(require_role('admin', 'analyst'))):
    """查看当前弱口令字典"""
    return APIResponse(data=db.get_weak_passwords(protocol=protocol))
