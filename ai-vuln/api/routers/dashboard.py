# -*- coding: utf-8 -*-
"""仪表盘 API"""
from fastapi import APIRouter, Depends
from api.dependencies import get_db
from api.auth import verify_api_key
from api.models import APIResponse

router = APIRouter()

@router.get('/dashboard/summary', response_model=APIResponse)
def dashboard_summary(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_statistics())

@router.get('/dashboard/charts/vuln-by-task', response_model=APIResponse)
def vuln_by_task(limit: int = 30, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_vuln_by_task(limit=limit))

@router.get('/dashboard/charts/asset-by-type', response_model=APIResponse)
def asset_by_type(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_asset_type_counts())

@router.get('/dashboard/charts/scan-types', response_model=APIResponse)
def scan_types(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_scan_type_counts())

@router.get('/dashboard/charts/today-status', response_model=APIResponse)
def today_status(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_today_status_counts())

@router.get('/dashboard/charts/audit-by-task', response_model=APIResponse)
def audit_by_task(limit: int = 30, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_audit_by_task(limit=limit))
