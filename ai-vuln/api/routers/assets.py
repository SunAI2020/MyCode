# -*- coding: utf-8 -*-
"""资产管理 API"""
from fastapi import APIRouter, Depends, Query
from api.dependencies import get_db, require_role
from api.auth import verify_api_key
from api.models import AssetCreate, AssetUpdate, AssetImportRequest, APIResponse, PaginatedResponse

router = APIRouter()

@router.get('/assets', response_model=PaginatedResponse)
def list_assets(type: str = Query(None), status: str = Query(None),
                keyword: str = Query(None), tags: str = Query(None),
                page: int = 1, page_size: int = 50,
                db=Depends(get_db), _=Depends(verify_api_key)):
    filters = {}
    if type: filters['type'] = type
    if status: filters['status'] = status
    if keyword: filters['keyword'] = keyword
    if tags: filters['tags'] = tags
    all_items = db.get_assets(filters=filters)
    total = len(all_items)
    start = (page - 1) * page_size
    return PaginatedResponse(total=total, page=page, page_size=page_size,
                             items=all_items[start:start + page_size])

@router.get('/assets/stats/types', response_model=APIResponse)
def asset_type_stats(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_asset_type_counts())

@router.get('/assets/tags', response_model=APIResponse)
def list_asset_tags(db=Depends(get_db), _=Depends(verify_api_key)):
    return APIResponse(data=db.get_asset_tags())

@router.post('/assets/import', response_model=APIResponse)
def import_assets(body: AssetImportRequest, db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    """批量导入资产（CSV 文本 或 base64 编码的 Excel）"""
    import base64
    from asset_importer import parse_csv, parse_excel, parse_tags, import_assets as _import
    try:
        if body.format == 'excel':
            assets, errors = parse_excel(base64.b64decode(body.data))
        else:
            assets, errors = parse_csv(body.data)
    except Exception as e:
        return APIResponse(success=False, message=f'解析失败: {e}')
    if body.tags:
        extra = parse_tags(body.tags)
        for a in assets:
            merged = parse_tags(a.get('tags', ''))
            a['tags'] = ','.join(merged + [t for t in extra if t not in merged])
    stats = _import(db, assets)
    return APIResponse(data={'stats': stats, 'errors': errors},
                       message=f"导入完成: 新增{stats['inserted']} 重复{stats['duplicate']} 失败{stats['failed']}")

@router.get('/assets/{asset_id}', response_model=APIResponse)
def get_asset(asset_id: int, db=Depends(get_db), _=Depends(verify_api_key)):
    a = db.get_asset(asset_id)
    return APIResponse(data=a) if a else APIResponse(success=False, message='Not found')

@router.post('/assets', status_code=201, response_model=APIResponse)
def create_asset(body: AssetCreate, db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    aid = db.add_asset(body.model_dump())
    return APIResponse(data={'id': aid}, message='Created') if aid != -1 else APIResponse(success=False, message='Duplicate IP/MAC')

@router.put('/assets/{asset_id}', response_model=APIResponse)
def update_asset(asset_id: int, body: AssetUpdate, db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    db.update_asset(asset_id, body.model_dump(exclude_none=True))
    return APIResponse(data=db.get_asset(asset_id), message='Updated')

@router.delete('/assets/{asset_id}', response_model=APIResponse)
def delete_asset(asset_id: int, db=Depends(get_db), _=Depends(require_role('admin', 'analyst'))):
    db.delete_asset(asset_id)
    return APIResponse(message='Deleted')
