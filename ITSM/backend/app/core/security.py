import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str | int, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


# ---- 字段级脱敏工具 ----

def mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return phone or ""
    return phone[:3] + "****" + phone[-4:]


def mask_ip(ip: str | None) -> str:
    if not ip:
        return ip or ""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    # IPv6（含冒号）或非标准格式：仅保留首个段，其余遮蔽，避免客户侧看到完整地址
    if ":" in ip:
        return ip.split(":")[0] + "::*"
    return "***"


def mask_amount(_value: float | None) -> str:
    return "***"  # 低权限角色金额遮蔽占位


def mask_text(text: str | None) -> str:
    """对报告等文本内容脱敏：身份证/银行卡/手机号/邮箱/IP，返回脱敏后的文本。"""
    if not text:
        return text or ""
    # 身份证（18 位，末位可 X）—— 先于银行卡/手机号，避免被长数字正则吞掉
    text = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "【身份证已脱敏】", text)
    # 银行卡（16-19 位）
    text = re.sub(
        r"(?<!\d)\d{16,19}(?!\d)",
        lambda m: m.group(0)[:6] + "****" + m.group(0)[-4:],
        text,
    )
    # 手机号（11 位）
    text = re.sub(
        r"(?<!\d)1[3-9]\d{9}(?!\d)",
        lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:],
        text,
    )
    # 邮箱
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "【邮箱已脱敏】", text)
    # IPv4
    text = re.sub(
        r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])",
        lambda m: ".".join(m.group(0).split(".")[:2]) + ".*.*",
        text,
    )
    return text


def mask_sensitive(data: dict, scope: int | None) -> dict:
    """客户侧角色（scope 非 None）对敏感字段脱敏；平台侧返回原文。就地修改并返回。"""
    if scope is None:
        return data
    if data.get("contact"):
        data["contact"] = mask_phone(data["contact"])
    if data.get("ip"):
        data["ip"] = mask_ip(data["ip"])
    for k in ("amount", "contract_price", "price", "dispatch_price"):
        if data.get(k) is not None:
            data[k] = mask_amount(data[k])
    return data


def masked_page(result: dict, scope: int | None) -> dict:
    """对分页结果 items 逐条脱敏。"""
    result["items"] = [mask_sensitive(i, scope) for i in result.get("items", [])]
    return result
