"""合同原件加密存储：Fernet 对称加密。

密钥来源优先级：
1. 环境变量 / settings.ARCHIVE_ENC_KEY（Fernet base64 32 字节）；
2. 本地持久化密钥文件 uploads/contracts/.archive.key（首次自动生成）。

刻意不派生自 SECRET_KEY —— 该密钥未在 .env 配置时每次启动随机，派生会导致
已落盘文件重启后无法解密。密钥文件方式跨重启稳定。
"""
import os

from cryptography.fernet import Fernet

from app.core.config import settings

_fernet: Fernet | None = None


def _key_path() -> str:
    return os.path.join(settings.UPLOAD_DIR, "contracts", ".archive.key")


def _load_or_create_key() -> bytes:
    env_key = getattr(settings, "ARCHIVE_ENC_KEY", "") or ""
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key
    path = _key_path()
    if os.path.exists(path):
        with open(path, "rb") as f:
            key = f.read().strip()
        if key:
            return key
    os.makedirs(os.path.dirname(path), exist_ok=True, mode=0o700)
    key = Fernet.generate_key()
    # 密钥文件仅属主可读写（Linux 生产防其他进程/账号读取）
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _get_fernet().decrypt(token)
