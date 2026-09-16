# -*- coding: utf-8 -*-
"""AI漏洞扫描系统 - SSRF 防护（目标地址范围校验）

Web 扫描 / HTTP 探测端点允许用户指定任意 http(s) 目标，若不约束目标地址，
已获 admin/analyst 授权的调用方就能把扫描器当 SSRF 代理打内网与云元数据。

防御策略：默认拒绝私网 / 环回 / 链路本地 / 保留地址，以及会被 DNS 解析到
这些地址的域名（localhost、*.nip.io、*.sslip.io 等）。确需扫描内网时
由调用方显式传 allow_internal=True，这是"知情选择"而非"误放行"。

只依赖标准库，不做任何到目标的连接；getaddrinfo 仅用于把域名解析成 IP
再判定归属，DNS 解析失败一律按拒绝处理（fail-closed）。
"""
import ipaddress
import socket
from urllib.parse import urlsplit

# 显式拒绝的主机名：不依赖 DNS 解析即可拦下的常见 SSRF 入口
_BLOCKED_HOSTNAMES = {
    'localhost', 'localhost.localdomain',
    'metadata', 'metadata.google.internal',
}

# 明确用于 SSRF 的解析服务后缀（任意子域解析到攻击者指定的内网 IP）
_BLOCKED_DOMAIN_SUFFIXES = ('.nip.io', '.sslip.io', '.localtest.me')


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_unspecified or ip.is_multicast
    )


def _resolve_blocked(url: str):
    """返回 (host, 是否内网) 或 None（解析失败）。"""
    text = str(url or '')
    if not text:
        return None
    parts = urlsplit(text)
    host = (parts.hostname or '').lower()
    if not host:
        return None
    if host in _BLOCKED_HOSTNAMES or host.endswith(_BLOCKED_DOMAIN_SUFFIXES):
        return host, True
    if _is_blocked_ip(host):
        return host, True
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == 'https' else 80),
                                   type=socket.SOCK_STREAM)
    except socket.gaierror:
        return host, None
    resolved = {info[4][0] for info in infos}
    return host, any(_is_blocked_ip(ip) for ip in resolved)


def tls_verify(url: str) -> bool:
    """按目标归属决定是否校验证书：公网目标强制校验证书，内网目标关闭校验。

    内网设备（自签名/内部 CA）校验会误报大量证书错误，故跳过；
    公网目标无此豁免，证书无效即应暴露给用户。
    解析失败默认要求校验证书（fail-closed）——扫公网时宁可报证书错误。
    """
    r = _resolve_blocked(url)
    if r is None:
        return True
    host, blocked = r
    if blocked is None:
        return True
    return not blocked


def ssrf_guard(url: str, allow_internal: bool = False) -> str:
    """校验目标 URL 是否指向受保护的内网地址。返回原 URL，否则抛 ValueError。"""
    if allow_internal:
        return url

    text = str(url or '')
    if not text:
        raise ValueError('目标地址为空')

    parts = urlsplit(text)
    host = (parts.hostname or '').lower()
    if not host:
        raise ValueError('无法从目标地址解析出主机名')

    # 1. 主机名直接命中黑名单
    if host in _BLOCKED_HOSTNAMES:
        raise ValueError(f'目标地址指向受限主机: {host}')

    # 2. 域名后缀命中 SSRF 解析服务
    if host.endswith(_BLOCKED_DOMAIN_SUFFIXES):
        raise ValueError(f'目标地址使用了 SSRF 解析服务: {host}')

    # 3. 直接给出 IP 字面量
    if _is_blocked_ip(host):
        raise ValueError(f'目标地址指向内网/受限地址: {host}')

    # 4. 域名解析到受保护地址（含 DNS rebinding 场景）
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == 'https' else 80),
                                   type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        # 解析失败意味着该域名要么不存在，要么被 SSRF 防护服务故意拒绝解析；
        # 扫描器无法确定目标在哪，一律拒绝。
        raise ValueError(f'目标地址无法解析，已拒绝: {host} ({e})')

    resolved = {info[4][0] for info in infos}
    if any(_is_blocked_ip(ip) for ip in resolved):
        raise ValueError(f'目标地址解析到内网/受限地址: {host} -> {sorted(resolved)}')

    return url
