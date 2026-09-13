# -*- coding: utf-8 -*-
"""用户认证 API"""
from fastapi import APIRouter, Depends

from api.dependencies import get_db, get_current_user
from api.models import LoginRequest, PasswordChange, APIResponse
from auth_rbac import verify_password, generate_token, hash_password

router = APIRouter()


@router.post('/auth/login', response_model=APIResponse)
def login(body: LoginRequest, db=Depends(get_db)):
    user = db.get_user_by_username(body.username)
    if not user or not verify_password(body.password, user['password_hash']):
        return APIResponse(success=False, message='用户名或密码错误')
    if not user.get('active', 1):
        return APIResponse(success=False, message='账号已停用')

    token = generate_token(user['username'], user['role'])
    db.record_login(user['id'])
    db.add_audit_log('login', 'user', user['id'], body.username)
    return APIResponse(data={
        'token': token,
        'user': {
            'id': user['id'], 'username': user['username'], 'role': user['role'],
            'full_name': user.get('full_name'),
            'must_change_password': user.get('must_change_password', 0),
        },
    })


@router.get('/auth/me', response_model=APIResponse)
def me(user=Depends(get_current_user), db=Depends(get_db)):
    u = db.get_user_by_username(user['sub'])
    if not u:
        return APIResponse(success=False, message='用户不存在')
    return APIResponse(data={
        'id': u['id'], 'username': u['username'], 'role': u['role'],
        'full_name': u.get('full_name'), 'email': u.get('email'),
        'must_change_password': u.get('must_change_password', 0),
    })


@router.post('/auth/change-password', response_model=APIResponse)
def change_password(body: PasswordChange, user=Depends(get_current_user), db=Depends(get_db)):
    u = db.get_user_by_username(user['sub'])
    if not u or not verify_password(body.old_password, u['password_hash']):
        return APIResponse(success=False, message='旧密码错误')
    db.set_user_password(u['id'], hash_password(body.new_password))
    db.add_audit_log('change_password', 'user', u['id'], u['username'])
    return APIResponse(message='密码已修改')
