# -*- coding: utf-8 -*-
"""依赖注入 — DB 实例 + 认证"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_db_instance = None

_bearer_scheme = HTTPBearer(auto_error=False)


def get_db_instance():
    global _db_instance
    if _db_instance is None:
        from database import Database
        _db_instance = Database()
    return _db_instance


def release_db_instance():
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None


def get_db() -> Generator:
    db = get_db_instance()
    try:
        yield db
    finally:
        pass


# ============================================================
# 用户认证 + RBAC（P1 用户+RBAC 系统）
# ============================================================
def _load_active_user(username: str, db) -> dict:
    """按用户名加载 DB 用户，校验存在性与 active 状态。

    防止：用户被删除或停用(active=0)后，其未过期令牌仍能继续访问。
    """
    db_user = db.get_user_by_username(username) if username else None
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户不存在或已被删除')
    if not db_user.get('active', 1):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='账号已停用')
    return db_user


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)) -> dict:
    """解析 Bearer token，返回 {sub, role, iat, exp}"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='未提供认证令牌')
    from auth_rbac import verify_token
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='令牌无效或已过期')
    # 校验用户存在且未停用，并以 DB 中的角色为准（防止降权后令牌仍携带旧角色）
    db_user = _load_active_user(payload.get('sub', ''), get_db_instance())
    payload['role'] = db_user.get('role', payload.get('role'))
    return payload


def require_role(*roles: str):
    """返回一个 FastAPI 依赖：校验当前用户角色 + 强制初始密码修改"""
    def _dependency(user: dict = Depends(get_current_user), db=Depends(get_db)) -> dict:
        if user.get('role') not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f'需要角色: {", ".join(roles)}')
        # 默认 admin/admin123 仅用于首次登录，未改密前禁止任何业务操作
        db_user = db.get_user_by_username(user.get('sub'))
        if db_user and db_user.get('must_change_password'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail='必须先修改初始密码')
        return user
    return _dependency
