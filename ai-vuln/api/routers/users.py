# -*- coding: utf-8 -*-
"""用户管理 API（admin 专属）"""
from fastapi import APIRouter, Depends

from api.dependencies import get_db, require_role
from api.models import UserCreate, UserUpdate, APIResponse
from auth_rbac import hash_password, ROLES

router = APIRouter()


@router.get('/users', response_model=APIResponse)
def list_users(db=Depends(get_db), _=Depends(require_role('admin'))):
    return APIResponse(data=db.get_users())


@router.get('/users/roles', response_model=APIResponse)
def list_roles(db=Depends(get_db), _=Depends(require_role('admin'))):
    return APIResponse(data=db.get_roles())


@router.post('/users', status_code=201, response_model=APIResponse)
def create_user(body: UserCreate, db=Depends(get_db), _=Depends(require_role('admin'))):
    if body.role not in ROLES:
        return APIResponse(success=False, message=f'非法角色: {body.role}')
    if db.get_user_by_username(body.username):
        return APIResponse(success=False, message='用户名已存在')
    uid = db.create_user(body.username, hash_password(body.password), role=body.role,
                         email=body.email, full_name=body.full_name, must_change_password=1)
    db.add_audit_log('create_user', 'user', uid, body.username)
    return APIResponse(data={'id': uid}, message='Created')


@router.put('/users/{user_id}', response_model=APIResponse)
def update_user(user_id: int, body: UserUpdate, db=Depends(get_db), _=Depends(require_role('admin'))):
    if not db.get_user(user_id):
        return APIResponse(success=False, message='用户不存在')
    if body.role is not None and body.role not in ROLES:
        return APIResponse(success=False, message=f'非法角色: {body.role}')
    db.update_user(user_id, **body.model_dump(exclude_none=True))
    db.add_audit_log('update_user', 'user', user_id)
    return APIResponse(data=db.get_user(user_id), message='Updated')


@router.delete('/users/{user_id}', response_model=APIResponse)
def delete_user(user_id: int, db=Depends(get_db), user=Depends(require_role('admin'))):
    current = db.get_user_by_username(user['sub'])
    if current and current['id'] == user_id:
        return APIResponse(success=False, message='不能删除自己')
    if not db.get_user(user_id):
        return APIResponse(success=False, message='用户不存在')
    db.delete_user(user_id)
    db.add_audit_log('delete_user', 'user', user_id)
    return APIResponse(message='Deleted')
