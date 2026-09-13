# -*- coding: utf-8 -*-
"""CVE 漏洞库 API"""
from fastapi import APIRouter, Depends, Query
from api.dependencies import get_db
from api.auth import verify_api_key
from api.models import APIResponse, PaginatedResponse

router = APIRouter()

@router.get('/cve/search', response_model=PaginatedResponse)
def search_cve(keyword: str = Query(None), min_cvss: float = Query(0, ge=0, le=10),
               page: int = 1, page_size: int = 50,
               db=Depends(get_db), _=Depends(verify_api_key)):
    total = db.count_cve(keyword=keyword, min_cvss=min_cvss)
    offset = (page - 1) * page_size
    items = db.search_cve(keyword=keyword, min_cvss=min_cvss, limit=page_size, offset=offset)
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)

@router.get('/cve/severity-distribution', response_model=APIResponse)
def severity_distribution(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_cve_by_severity())

@router.get('/cve/recent-high-risk', response_model=APIResponse)
def recent_high_risk(limit: int = 50, days: int = 90,
                     db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.cve.get_top_recent_cves(limit=limit, days=days))

@router.get('/cve/{cve_id}', response_model=APIResponse)
def get_cve_detail(cve_id: str, db=Depends(get_db), _=Depends(verify_api_key)):
    results = db.search_cve(keyword=cve_id, limit=1)
    return APIResponse(data=results[0]) if results else APIResponse(success=False, message='Not found')
