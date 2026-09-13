# -*- coding: utf-8 -*-
"""SSRF 防护测试 — 内网/环回/链路本地/云元数据阻断"""
import pytest

from ssrf_guard import ssrf_guard, tls_verify


# ============================================================
# IP 字面量（不依赖 DNS，确定性断言）
# ============================================================
@pytest.mark.parametrize('url', [
    'http://127.0.0.1/',
    'http://127.0.0.1:8080/admin',
    'http://localhost/',
    'http://10.0.0.1/',
    'http://172.16.0.1/',
    'http://192.168.1.1/',
    'http://169.254.169.254/latest/meta-data/',      # 云元数据
    'http://[::1]/',
    'http://[fe80::1]/',
    'http://0.0.0.0/',
])
def test_blocks_internal_addresses(url):
    with pytest.raises(ValueError):
        ssrf_guard(url)


@pytest.mark.parametrize('url', [
    'http://localhost',
    'http://metadata.google.internal/',
    'http://a.nip.io/',
    'http://x.sslip.io/',
    'http://y.localtest.me/',
])
def test_blocks_known_ssrf_hostnames(url):
    with pytest.raises(ValueError):
        ssrf_guard(url)


@pytest.mark.parametrize('url', [
    'http://8.8.8.8/',
    'http://93.184.216.34/',      # example.com 的公网 IP
])
def test_allows_public_targets(url):
    assert ssrf_guard(url) == url


def test_allow_internal_is_server_side_only():
    """allow_internal 是 ssrf_guard 的内部参数，服务端当前恒传 False；
    请求模型不得暴露该开关，否则客户端自填 true 就绕过了防护"""
    assert ssrf_guard('http://10.0.0.1/', allow_internal=True) == 'http://10.0.0.1/'
    with pytest.raises(ValueError):
        ssrf_guard('http://10.0.0.1/')


def test_empty_url_rejected():
    with pytest.raises(ValueError):
        ssrf_guard('')


def test_nonexistent_domain_rejected():
    """解析失败 fail-closed：不知道目标在哪就拒绝"""
    with pytest.raises(ValueError):
        ssrf_guard('http://definitely-not-a-real-host-9x7q.invalid/')


# ============================================================
# TLS 证书校验策略：公网强制校验，内网关闭
# ============================================================
class TestTlsVerify:
    @pytest.mark.parametrize('url', [
        'https://8.8.8.8/',
        'https://93.184.216.34/',
    ])
    def test_public_target_enforces_verify(self, url):
        assert tls_verify(url) is True

    @pytest.mark.parametrize('url', [
        'https://127.0.0.1/',
        'https://10.0.0.1/',
        'https://192.168.1.1/',
        'https://169.254.169.254/',
        'https://[::1]/',
        'https://[fe80::1]/',
    ])
    def test_internal_target_skips_verify(self, url):
        assert tls_verify(url) is False

    def test_localhost_skips_verify(self):
        assert tls_verify('https://localhost/') is False

    def test_ssrf_hostname_skips_verify(self):
        assert tls_verify('https://a.nip.io/') is False

    def test_unresolvable_fails_closed_to_verify(self):
        """解析失败时默认要求校验证书，宁可报证书错误"""
        assert tls_verify('https://definitely-not-real-7k2q.invalid/') is True

    def test_empty_url_fails_closed(self):
        assert tls_verify('') is True


# ============================================================
# 模型层接线
# ============================================================
def test_web_scan_request_blocks_internal():
    from api.models import WebScanRequest
    with pytest.raises(Exception):
        WebScanRequest(target_url='http://169.254.169.254/latest/meta-data/')


def test_web_scan_request_has_no_client_bypass():
    """请求体不再接受 allow_internal —— 客户端无法自选放行内网"""
    from api.models import WebScanRequest
    with pytest.raises(Exception):
        WebScanRequest(target_url='http://10.0.0.1/', allow_internal=True)


def test_http_probe_request_blocks_internal():
    from api.models import HTTPProbeRequest
    with pytest.raises(Exception):
        HTTPProbeRequest(target_url='http://127.0.0.1/', path='/')


def test_http_probe_request_allows_public_ip():
    from api.models import HTTPProbeRequest
    req = HTTPProbeRequest(target_url='http://8.8.8.8/', path='/')
    assert req.target_url == 'http://8.8.8.8/'


def test_non_http_scheme_still_rejected():
    from api.models import WebScanRequest
    with pytest.raises(Exception):
        WebScanRequest(target_url='file:///etc/passwd')
