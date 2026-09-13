# -*- coding: utf-8 -*-
"""威胁情报 API"""
from fastapi import APIRouter, Depends, Query
from api.dependencies import get_db
from api.auth import verify_api_key
from api.models import APIResponse

router = APIRouter()

@router.get('/threat-intel/kev', response_model=APIResponse)
def list_kev(limit: int = 1000, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_kev_list(limit=limit))

@router.get('/threat-intel/epss/{cve_id}', response_model=APIResponse)
def get_epss(cve_id: str, db=Depends(get_db), _=Depends(verify_api_key)):
    epss = db.intel.get_epss(cve_id)
    return APIResponse(data=epss) if epss else APIResponse(success=False, message='Not found')

@router.get('/threat-intel/actors', response_model=APIResponse)
def list_actors(limit: int = 100, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.intel.get_threat_actors(limit=limit))

@router.get('/threat-intel/iocs', response_model=APIResponse)
def search_iocs(keyword: str = Query(None), ioc_type: str = Query(None),
                limit: int = 1000, db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.intel.search_iocs(keyword=keyword, ioc_type=ioc_type, limit=limit))

@router.get('/threat-intel/stats', response_model=APIResponse)
def intel_stats(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_intel_statistics())
