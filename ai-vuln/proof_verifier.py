# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - proof-based 证据验证模块

对标 Invicti 的 proof-based scanning：用【安全、可逆】的确定性验证确认漏洞
真实存在，而非仅凭模式匹配。与 AI 核验互补：AI 判断语义误报，proof 给出
确定性可利用证据。

当前支持两类安全验证（均不破坏目标、不拖库）：
- 布尔盲注 SQLi：' AND '1'='1 vs ' AND '1'='2 的响应差分 → 证明注入点存在
- 反射型 XSS：唯一随机 token 的【未编码】回显 → 证明输出未做 HTML 转义
"""
import logging
import random
import re
import string
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_boolean_sqli_pair() -> Tuple[str, str]:
    """返回 (真条件 payload, 假条件 payload)，用于布尔盲注差分验证。"""
    return ("' AND '1'='1", "' AND '1'='2")


def build_xss_proof_token() -> Tuple[str, str]:
    """返回 (唯一 token, 带 token 的 payload)。token 用于检测未编码回显。"""
    token = 'p' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    payload = f"<script>{token}</script>"
    return token, payload


_DYNAMIC_RE = re.compile(
    r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'
    r'|\b\d{10,13}\b'
    r'|(?:csrf|session|nonce|token|xsrf|timestamp)[_\-]?[\w]*["\']?\s*[:=]\s*["\']?[A-Za-z0-9_\-]+',
    re.IGNORECASE,
)


def _normalize_for_comparison(text: str) -> str:
    """剔除时间戳/随机 token 等动态内容，降低布尔差分误判。"""
    if not text:
        return ''
    return _DYNAMIC_RE.sub('', text)


def is_boolean_differential(true_text: str, false_text: str,
                            min_diff_ratio: float = 0.05) -> bool:
    """判断真假条件响应是否产生有意义差异（布尔盲注判据）。

    先剔除时间戳/随机 token 等动态内容再比较长度差，避免把 CSRF/会话/广告
    等无害噪声误判为注入证据。返回 True 仅表示「疑似存在稳定差分」，
    并非确定性证明，仍建议结合其他信号综合判断。
    """
    if true_text is None or false_text is None:
        return False
    a = _normalize_for_comparison(true_text)
    b = _normalize_for_comparison(false_text)
    if a == b:
        return False
    max_len = max(len(a), len(b), 1)
    diff_len = abs(len(a) - len(b))
    return diff_len / max_len >= min_diff_ratio


def is_token_reflected_unencoded(response_text: str, token: str) -> bool:
    """判断唯一 token 是否被【未编码】回显（反射型 XSS 判据）。

    仅当 token 原样出现、且紧邻的 '<' 未被转义为 '&lt;' 时才判为真实
    可执行上下文，避免把已做 HTML 编码的输出误判为 XSS。
    """
    if not response_text or not token:
        return False
    if token not in response_text:
        return False
    idx = response_text.index(token)
    context = response_text[max(0, idx - 30):idx]
    return '&lt;' not in context


class ProofVerifier:
    """proof-based 验证器 — 对注入点做确定性确认。

    inject_fn(url, surface, param, payload) -> response|None，由调用方注入，
    通常绑定 WebVulnScanner._inject_and_get。
    """

    def __init__(self, inject_fn):
        self.inject_fn = inject_fn

    def verify_boolean_sqli(self, url, surface, param) -> Optional[Dict]:
        """布尔盲注差分验证。返回 {'verified': bool, 'evidence': str} 或 None。"""
        true_payload, false_payload = build_boolean_sqli_pair()
        try:
            r_true = self.inject_fn(url, surface, param, true_payload)
            r_false = self.inject_fn(url, surface, param, false_payload)
        except Exception as e:
            logger.debug(f"布尔验证失败: {e}")
            return None
        if r_true is None or r_false is None:
            return None
        true_text = getattr(r_true, 'text', '') or ''
        false_text = getattr(r_false, 'text', '') or ''
        verified = is_boolean_differential(true_text, false_text)
        return {
            'verified': verified,
            'evidence': f'布尔盲注差分: 真条件 {len(true_text)}B vs 假条件 {len(false_text)}B',
        }

    def verify_reflected_xss(self, url, surface, param) -> Optional[Dict]:
        """XSS 唯一 token 未编码回显验证。返回 {'verified': bool, 'evidence': str} 或 None。"""
        token, payload = build_xss_proof_token()
        try:
            r = self.inject_fn(url, surface, param, payload)
        except Exception as e:
            logger.debug(f"XSS 验证失败: {e}")
            return None
        if r is None:
            return None
        text = getattr(r, 'text', '') or ''
        verified = is_token_reflected_unencoded(text, token)
        return {'verified': verified,
                'evidence': f'唯一 token {token} 未编码回显' if verified else f'token {token} 未以可执行形式回显'}


__all__ = [
    'build_boolean_sqli_pair', 'build_xss_proof_token',
    'is_boolean_differential', 'is_token_reflected_unencoded', 'ProofVerifier',
]
