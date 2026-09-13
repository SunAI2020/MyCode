# -*- coding: utf-8 -*-
"""API 认证 — API Key + Bearer token（P1 RBAC）"""
import os
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

API_KEY_HEADER = APIKeyHeader(name='X-API-Key', auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    api_key: str = Security(API_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> str:
    """认证：优先接受有效 Bearer token（RBAC），回退到 X-API-Key"""
    # 1. Bearer token（前端 RBAC 登录）
    if credentials is not None:
        try:
            from auth_rbac import verify_token
            payload = verify_token(credentials.credentials)
        except Exception:
            payload = None
        if payload:
            from api.dependencies import get_db_instance, _load_active_user
            db = get_db_instance()
            # 校验用户存在且未停用（停用/删除后令牌立即失效）
            db_user = _load_active_user(payload.get('sub', ''), db)
            if db_user.get('must_change_password'):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail='必须先修改初始密码')
            return payload.get('sub', '')
    # 2. X-API-Key（第三方集成）
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='X-API-Key header or Bearer token required')
    valid_key = os.getenv('API_KEY', '')
    if not valid_key:
        try:
            from api.dependencies import get_db_instance
            db = get_db_instance()
            valid_key = db.get_setting('api_key', '')
        except Exception:
            pass
    if not valid_key:
        # 无配置时生成随机密钥并持久化，避免硬编码默认值
        import secrets
        valid_key = secrets.token_urlsafe(32)
        try:
            from api.dependencies import get_db_instance
            db = get_db_instance()
            db.set_setting('api_key', valid_key)
        except Exception:
            pass
    if api_key != valid_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='Invalid API key')
    return api_key
