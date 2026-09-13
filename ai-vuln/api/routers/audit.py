# -*- coding: utf-8 -*-
"""代码审计 API"""
from fastapi import APIRouter, Depends
from api.dependencies import get_db
from api.auth import verify_api_key
from api.models import APIResponse

router = APIRouter()

@router.get('/audit/history', response_model=APIResponse)
def audit_history(limit: int = 100, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_audit_history(limit=limit))

@router.get('/audit/{audit_id}', response_model=APIResponse)
def audit_detail(audit_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    for h in db.get_audit_history(limit=99999):
        if h['id'] == audit_id:
            return APIResponse(data=h)
    return APIResponse(success=False, message='Not found')
