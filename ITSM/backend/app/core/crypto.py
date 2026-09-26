"""字段级加密：Fernet 可逆加密 + SQLAlchemy 列类型。

密钥由 settings.SECRET_KEY 经 SHA-256 派生（32 字节 → urlsafe base64），
密文带 ``enc:v1:`` 前缀；解密遇到非前缀值（历史明文）原样返回，实现无迁移平滑升级。
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import settings

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_field(plaintext: str) -> str:
    """加密字段，返回带版本前缀的密文。"""
    return _PREFIX + _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_field(value: str) -> str:
    """解密字段；非密文（无前缀）原样返回，兼容历史明文数据。"""
    if not value or not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return value  # 损坏/篡改密文按明文兜底，避免读失败


class EncryptedText(TypeDecorator):
    """透明加解密的文本列类型（impl 仍为 TEXT，无 DDL 变更）。"""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_field(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_field(value)
