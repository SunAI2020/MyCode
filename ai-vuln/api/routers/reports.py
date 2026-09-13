# -*- coding: utf-8 -*-
"""报告 API"""
import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from api.dependencies import get_db, require_role
from api.auth import verify_api_key
from api.models import APIResponse

router = APIRouter()

@router.get('/reports', response_model=APIResponse)
def list_reports(limit: int = 50, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_reports(limit=limit))

@router.get('/reports/{report_id}', response_model=APIResponse)
def get_report(report_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    for r in db.get_reports(limit=99999):
        if r['id'] == report_id:
            return APIResponse(data=r)
    return APIResponse(success=False, message='Not found')

@router.get('/reports/{report_id}/download')
def download_report(report_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    for r in db.get_reports(limit=99999):
        if r['id'] == report_id and r.get('file_path'):
            path = r['file_path']
            if os.path.exists(path):
                return FileResponse(path, filename=os.path.basename(path))
    return APIResponse(success=False, message='File not found')

@router.delete('/reports/{report_id}', response_model=APIResponse)
def delete_report(report_id: int, db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    db.delete_report(report_id)
    return APIResponse(message='Deleted')
