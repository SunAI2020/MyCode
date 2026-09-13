# -*- coding: utf-8 -*-
"""CCMS 安全模块 — JWT 令牌 + 密码哈希"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from ..config import settings

# 算法
ALGORITHM = settings.jwt_algorithm
SECRET_KEY = settings.jwt_secret_key


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    if not plain_password or not hashed_password:
        return False
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except (ValueError, TypeError, AttributeError):
        return False


def create_access_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """创建 JWT 访问令牌"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, datetime]:
    """创建 JWT 刷新令牌，返回 (token, expires_at)"""
    if expires_delta is None:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), expires_at


def decode_token(token: str) -> dict:
    """解码并验证 JWT 令牌，返回 payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"无效的令牌: {e}")


def get_user_id_from_token(token: str) -> UUID:
    """从 JWT 令牌中提取 user_id"""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise ValueError("令牌类型不正确")
    return UUID(payload["sub"])
