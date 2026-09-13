# -*- coding: utf-8 -*-
"""Web 应用安全扫描 API（异步任务 + 轮询）"""
from fastapi import APIRouter, Depends, Query, BackgroundTasks

from api.dependencies import get_db, require_role, get_current_user
from api.models import WebScanRequest, HTTPProbeRequest, APIResponse
from api.scan_jobs import create_job, update_job, get_job
from web_scanner import WebSecurityScanner, HTTPProber

router = APIRouter()


def _run_web_scan(job_id: str, target_url: str, do_directory: bool, do_zap: bool,
                  do_active: bool, ai_enabled: bool, db):
    """后台执行 Web 扫描（BackgroundTasks 线程池中运行）"""
    try:
        update_job(job_id, 'running')
        scanner = WebSecurityScanner(db=db, ai_enabled=ai_enabled)
        result = scanner.scan(target_url, do_directory=do_directory, do_zap=do_zap,
                              do_active=do_active)
        update_job(job_id, 'completed', result=result)
    except Exception as e:
        update_job(job_id, 'failed', error=str(e))


@router.post('/webscan', response_model=APIResponse)
def run_web_scan(body: WebScanRequest, background: BackgroundTasks,
                 db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    """提交 Web 安全扫描任务（异步），返回 job_id 供轮询"""
    job_id = create_job()
    background.add_task(_run_web_scan, job_id, body.target_url,
                        body.do_directory, body.do_zap, body.do_active, body.ai_enabled, db)
    return APIResponse(data={'job_id': job_id}, message='扫描任务已提交')


@router.get('/webscan/jobs/{job_id}', response_model=APIResponse)
def get_scan_job(job_id: str, _=Depends(require_role('admin', 'analyst'))):
    """轮询任务状态（与提交端点同角色门控，防 IDOR）"""
    job = get_job(job_id)
    if not job:
        return APIResponse(success=False, message='任务不存在或已过期')
    return APIResponse(data=job)


@router.get('/webscan/results', response_model=APIResponse)
def list_web_scan_results(target: str = Query(None), db=Depends(get_db),
                          _=Depends(get_current_user)):
    return APIResponse(data=db.get_web_scan_results(target=target))


@router.post('/webscan/probe', response_model=APIResponse)
def http_probe(body: HTTPProbeRequest, _=Depends(require_role('admin', 'analyst'))):
    """自定义 HTTP 请求探测（轻量，同步）"""
    prober = HTTPProber()
    url = body.target_url.rstrip('/') + body.path
    # 不自动跟随重定向：否则一个公网 URL 302 跳转回 169.254.169.254 就绕过了 SSRF 校验
    result = prober.probe(url, method=body.method, headers=body.headers, body=body.body,
                          follow_redirects=False)
    return APIResponse(data=result)
