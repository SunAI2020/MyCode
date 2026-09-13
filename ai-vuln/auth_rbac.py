# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - 用户认证与 RBAC 权限系统"""
import os
import hmac
import json
import time
import base64
import hashlib
import secrets
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# 角色权限矩阵（P1 用户+RBAC 系统）
# ============================================================
ROLES: Dict[str, List[str]] = {
    'admin': ['*'],  # 全权
    'analyst': [
        'asset:read', 'asset:write',
        'scan:read', 'scan:write',
        'web:scan', 'weakpass:scan',
        'workflow:read', 'workflow:write',
        'cve:read', 'intel:read', 'audit:read',
    ],
    'auditor': ['asset:read', 'scan:read', 'workflow:read', 'cve:read', 'intel:read', 'audit:read'],
    'viewer': ['asset:read', 'scan:read', 'cve:read'],
}

ROLE_LABELS: Dict[str, str] = {
    'admin': '系统管理员',
    'analyst': '安全分析员',
    'auditor': '审计员',
    'viewer': '只读用户',
}

PBKDF2_ITERATIONS = 100_000
DEFAULT_TOKEN_TTL = 12 * 3600  # 12 小时
_SECRET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.token_secret')


# ============================================================
# 密码哈希（pbkdf2_sha256，标准库，未来可替换为 bcrypt）
# ============================================================
def hash_password(password: str) -> str:
    """生成 pbkdf2_sha256 密码哈希：pbkdf2_sha256$iterations$salt_b64$dk_b64"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return 'pbkdf2_sha256${}${}${}'.format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode('ascii'),
        base64.b64encode(dk).decode('ascii'),
    )


def verify_password(password: str, stored: str) -> bool:
    """校验密码（常数时间比较，防时序攻击）"""
    try:
        algo, iters, salt_b64, dk_b64 = stored.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        salt = base64.b64decode(salt_b64.encode('ascii'))
        expected = base64.b64decode(dk_b64.encode('ascii'))
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ============================================================
# HMAC-SHA256 签名令牌（JWT 风格，零第三方依赖）
# ============================================================
def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64decode(data: str) -> bytes:
    pad = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode('ascii'))


def _get_secret(secret: Optional[str] = None) -> str:
    """令牌签名密钥：优先入参 → 环境变量 → 本地持久化随机密钥（无硬编码）"""
    if secret:
        return secret
    env = os.getenv('TOKEN_SECRET')
    if env:
        return env
    try:
        with open(_SECRET_FILE, 'r', encoding='utf-8') as f:
            key = f.read().strip()
            if key:
                return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    try:
        with open(_SECRET_FILE, 'w', encoding='utf-8') as f:
            f.write(key)
    except OSError:
        logger.warning(f"无法持久化令牌密钥到 {_SECRET_FILE}，本次运行使用临时密钥")
    return key


def generate_token(username: str, role: str, ttl_seconds: Optional[int] = None,
                   secret: Optional[str] = None) -> str:
    """生成签名令牌，载荷含 sub/role/iat/exp"""
    ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TOKEN_TTL
    header = {'alg': 'HS256', 'typ': 'JWT'}
    now = int(time.time())
    payload = {'sub': username, 'role': role, 'iat': now, 'exp': now + ttl}
    h = _b64encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    p = _b64encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    msg = f'{h}.{p}'.encode('utf-8')
    sig = _b64encode(hmac.new(_get_secret(secret).encode('utf-8'), msg, hashlib.sha256).digest())
    return f'{h}.{p}.{sig}'


def verify_token(token: str, secret: Optional[str] = None) -> Optional[Dict]:
    """校验令牌，成功返回载荷 dict，失败/过期返回 None"""
    try:
        h, p, s = token.split('.')
        msg = f'{h}.{p}'.encode('utf-8')
        expected_sig = hmac.new(_get_secret(secret).encode('utf-8'), msg, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64decode(s)):
            return None
        payload = json.loads(_b64decode(p).decode('utf-8'))
        if payload.get('exp', 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def has_permission(role: str, permission: str) -> bool:
    """检查角色是否拥有某权限"""
    perms = ROLES.get(role, [])
    return '*' in perms or permission in perms
