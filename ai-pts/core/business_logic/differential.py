"""
业务逻辑漏洞的确定性差分验证（神经-符号中的"符号"部分）。

借鉴 AUTHSENTRY 的多角色差分验证：用 owner 与 attacker 两个会话重放同一请求，
用确定性判据（状态码 + 响应体相似度）判定 IDOR/BOLA/越权，不依赖 LLM 当"裁判"，
从而抑制幻觉误报。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict


@dataclass
class HttpResponse:
    status: int
    body: str = ""
    headers: Dict = field(default_factory=dict)


_WS_RE = re.compile(r"\s+")


def _normalize(body: str) -> str:
    return _WS_RE.sub("", body or "").strip()


def _similar(a: str, b: str) -> bool:
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.9


def analyze_authorization(owner: HttpResponse, attacker: HttpResponse,
                          resource_id: str = "", expect_denied: bool = False) -> Dict:
    """确定性判定 owner/attacker 双响应是否构成越权/IDOR。

    Returns:
        {"finding_type": "idor"|"access_control_bypass"|"none", "confidence", "reason"}。
    """
    owner_ok = 200 <= owner.status < 300
    if not owner_ok:
        return {"finding_type": "none", "confidence": "low",
                "reason": "owner 自身访问失败，无越权判定基线"}

    attacker_ok = 200 <= attacker.status < 300

    if expect_denied and attacker_ok:
        return {"finding_type": "access_control_bypass", "confidence": "high",
                "reason": f"本应拒绝的请求（{resource_id or '资源'}）被 attacker 访问成功（{attacker.status}）"}

    if attacker_ok and _similar(owner.body, attacker.body):
        return {"finding_type": "idor", "confidence": "high",
                "reason": "attacker 响应与 owner 高度相似，疑似越权读取同一资源"}

    if attacker_ok and resource_id and resource_id in (attacker.body or ""):
        return {"finding_type": "idor", "confidence": "medium",
                "reason": f"资源标识 {resource_id} 出现在 attacker 响应中"}

    return {"finding_type": "none", "confidence": "low",
            "reason": "attacker 未获取到 owner 资源内容（无越权迹象）"}
