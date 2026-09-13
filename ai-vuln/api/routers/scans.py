# -*- coding: utf-8 -*-
"""扫描任务 API"""
from fastapi import APIRouter, Depends, Query
from api.dependencies import get_db, require_role
from api.auth import verify_api_key
from api.models import ScanTaskCreate, APIResponse, PaginatedResponse

router = APIRouter()

@router.get('/scans', response_model=PaginatedResponse)
def list_scans(page: int = 1, page_size: int = 50,
               db=Depends(get_db), _=Depends(verify_api_key)):
    page_size = max(1, min(page_size, 500))
    total = db.count_tasks()
    start = (page - 1) * page_size
    items = db.get_all_tasks(limit=page_size, offset=start)
    return PaginatedResponse(total=total, page=page, page_size=page_size,
                             items=items)

@router.get('/scans/{task_id}', response_model=APIResponse)
def get_scan(task_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    task = db.get_task(task_id)
    return APIResponse(data=task) if task else APIResponse(success=False, message='Not found')

@router.post('/scans', status_code=201, response_model=APIResponse)
def create_scan(body: ScanTaskCreate, db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    tid = db.create_task(body.target, body.scan_type, body.config)
    return APIResponse(data={'id': tid}, message='Created')

@router.get('/scans/{task_id}/results', response_model=APIResponse)
def get_scan_results(task_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_task_results(task_id))

@router.patch('/scans/{task_id}/status', response_model=APIResponse)
def update_scan_status(task_id: int, status: str = Query(...),
                       vuln_count: int = 0, error: str = '',
                       db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    db.update_task_status(task_id, status, vuln_count, error)
    return APIResponse(message='Updated')
