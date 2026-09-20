"""
双角色 HTTP 执行器（神经-符号中「确定性重放」的执行端）。

持有 owner/attacker 两套认证会话，按 role 用对应会话发送 HTTP 请求，返回
HttpResponse(status, body, headers)。含 SSRF/白名单 guard：仅放行授权目标主机
的 http/https 请求，且禁用重定向跟随（防重定向绕过 SSRF）。
"""
from __future__ import annotations

import warnings
from typing import Dict, Optional
from urllib.parse import urlparse

import requests

from core.business_logic.differential import HttpResponse


class DualRoleHttpExecutor:
    """owner/attacker 双会话 HTTP 重放执行器。

    sessions 形如::
        {
            "owner":    {"headers": {"Cookie": "session=..."}, "cookies": {...}},
            "attacker": {"headers": {"Cookie": "session=..."}},
        }

    用法：executor(method, url, role) -> HttpResponse；role 对应 sessions 的 key。
    """

    def __init__(self, base_url: str, sessions: Dict[str, Dict],
                 allowed_hosts: Optional[set] = None, timeout: int = 10,
                 verify: bool = True):
        # verify 默认 True 校验证书；仅授权自签证书目标经显式 opt-in 置 False。
        self.base_url = (base_url or "").rstrip("/")
        self.sessions = sessions or {}
        self.timeout = timeout
        self.verify = verify
        self.allowed_hosts = allowed_hosts or set()
        if self.base_url:
            p = urlparse(self.base_url)
            if not p.hostname:
                raise ValueError(f"base_url 缺少有效主机名: {base_url!r}")
            self.allowed_hosts.add(p.hostname.lower())

    def _resolve(self, url: str) -> str:
        u = (url or "").strip()
        if "://" in u:
            # 任何带 scheme 的绝对 URL（含 file/gopher 等）原样返回，交由 _ssrf_ok 校验 scheme
            return u
        return self.base_url + ("/" + u.lstrip("/") if u else "")

    def _ssrf_ok(self, url: str) -> bool:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = (p.hostname or "").lower()
        if not host:
            return False
        # fail-closed：空白名单 = 拒绝一切，防止空 allowlist 授权任意主机
        if not self.allowed_hosts or host not in self.allowed_hosts:
            return False
        return True

    def __call__(self, method: str, url: str, role: str) -> HttpResponse:
        full = self._resolve(url)
        if not self._ssrf_ok(full):
            return HttpResponse(status=0, body="", headers={})
        session = self.sessions.get(role) or {}
        headers = dict(session.get("headers") or {})
        cookies = dict(session.get("cookies") or {})
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # 自测环境常见自签证书
                resp = requests.request(
                    method=(method or "GET").upper(),
                    url=full,
                    headers=headers,
                    cookies=cookies,
                    timeout=self.timeout,
                    allow_redirects=False,
                    verify=self.verify,
                )
            return HttpResponse(
                status=resp.status_code, body=resp.text, headers=dict(resp.headers))
        except Exception:
            # 网络失败/非法 method 等 → 无基线，交由上层判「无越权迹象」
            return HttpResponse(status=0, body="", headers={})
