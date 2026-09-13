# -*- coding: utf-8 -*-
"""CCMS FastAPI 依赖注入"""

from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .core.security import get_user_id_from_token
from .database import get_db


async def get_current_user_id(
    request: Request,
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
) -> UUID:
    """从 JWT 令牌提取当前用户 ID（支持 Header 和 Cookie）"""
    token: str | None = None

    # 优先从 Authorization Header 提取
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()

    # 回退到 httpOnly Cookie（Web 端）
    if not token and access_token:
        token = access_token

    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    try:
        return get_user_id_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# 常用依赖简写
CurrentUser = Depends(get_current_user_id)
DbSession = Depends(get_db)
