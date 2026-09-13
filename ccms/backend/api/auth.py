# -*- coding: utf-8 -*-
"""认证 API — 注册、登录、刷新、注销"""

import hashlib
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import AuthenticationError, ConflictError
from ..core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..deps import DbSession, get_current_user_id
from ..models.user import RefreshToken, User

router = APIRouter(tags=["认证"])


# ── Pydantic Schemas ──

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class UserResponse(BaseModel):
    """用户信息响应"""
    id: uuid.UUID
    username: str
    email: str
    display_name: str
    role: str

    model_config = {"from_attributes": True}


# ── 端点 ──

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = DbSession):
    """用户注册"""
    # 检查用户名是否已存在
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise ConflictError("用户名已被注册")

    # 检查邮箱是否已存在
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise ConflictError("邮箱已被注册")

    # 创建用户
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.flush()

    # 生成令牌
    return await _generate_tokens(user, db)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = DbSession):
    """用户登录"""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise AuthenticationError("用户名或密码错误")

    if not user.is_active:
        raise AuthenticationError("账户已被禁用")

    return await _generate_tokens(user, db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, db: AsyncSession = DbSession):
    """刷新访问令牌（轮换机制）"""
    # 解码并验证刷新令牌
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationError("令牌类型不正确")
    except ValueError:
        raise AuthenticationError("刷新令牌无效或已过期")

    user_id = uuid.UUID(payload["sub"])

    # 验证刷新令牌在数据库中
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    stored_token = result.scalar_one_or_none()

    if not stored_token:
        # 刷新令牌可能已被盗用，撤销该用户所有刷新令牌
        await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        raise AuthenticationError("刷新令牌已被撤销，请重新登录")

    # 撤销旧刷新令牌
    stored_token.revoked = True

    # 获取用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("用户不存在")

    return await _generate_tokens(user, db)


@router.post("/logout", status_code=204)
async def logout(req: RefreshRequest, db: AsyncSession = DbSession):
    """注销 — 撤销刷新令牌"""
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored_token = result.scalar_one_or_none()
    if stored_token:
        stored_token.revoked = True


@router.get("/me", response_model=UserResponse)
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = DbSession,
):
    """获取当前用户信息"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("用户不存在")
    return user


# ── 辅助函数 ──

async def _generate_tokens(user: User, db: AsyncSession) -> TokenResponse:
    """生成访问/刷新令牌对"""
    access_token = create_access_token(user.id)
    refresh_token_str, expires_at = create_refresh_token(user.id)

    # 存储刷新令牌哈希
    token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(refresh_record)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=60 * 30,  # 30 分钟
    )
