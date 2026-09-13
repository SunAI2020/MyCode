# -*- coding: utf-8 -*-
"""proof_verifier 模块单元测试 — 纯逻辑（不依赖网络）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proof_verifier import (
    build_boolean_sqli_pair, build_xss_proof_token,
    is_boolean_differential, is_token_reflected_unencoded, ProofVerifier,
)


def test_boolean_sqli_pair_differs():
    true_p, false_p = build_boolean_sqli_pair()
    assert true_p != false_p
    assert "1'='1" in true_p and "1'='2" in false_p


def test_xss_token_unique_and_embedded():
    token, payload = build_xss_proof_token()
    assert token in payload
    assert len(token) == 13  # 'p' + 12 随机字符


def test_boolean_differential_true():
    assert is_boolean_differential("A" * 1000, "B" * 500) is True


def test_boolean_differential_identical_false():
    assert is_boolean_differential("same", "same") is False


def test_boolean_differential_tiny_diff_false():
    # 差异 < 5% → 不判为有意义差分
    assert is_boolean_differential("A" * 100, "A" * 99) is False


def test_boolean_differential_none_false():
    assert is_boolean_differential(None, "x") is False


def test_boolean_differential_ignores_dynamic_tokens():
    # 仅时间戳/CSRF token 不同 → 归一化后相同，不判为差分（避免噪声误报）
    a = '<html>result</html> csrf_token=abc123 2024-01-01 12:00:00'
    b = '<html>result</html> csrf_token=xyz789 2024-01-01 12:00:05'
    assert is_boolean_differential(a, b) is False


def test_token_reflected_unencoded_true():
    assert is_token_reflected_unencoded('<html><script>pabc123</script></html>', 'pabc123') is True


def test_token_reflected_encoded_false():
    # &lt; 说明已 HTML 编码，非真实 XSS
    assert is_token_reflected_unencoded('&lt;script&gt;pabc123&lt;/script&gt;', 'pabc123') is False


def test_token_absent_false():
    assert is_token_reflected_unencoded('<html></html>', 'pabc123') is False


class FakeResp:
    def __init__(self, text):
        self.text = text


def test_proof_verifier_boolean_sqli():
    # 真条件返回长页，假条件返回短页 → 差分确认
    verifier = ProofVerifier(
        lambda url, s, p, payload: FakeResp("A" * 1000 if "1'='1" in payload else "B" * 500))
    r = verifier.verify_boolean_sqli('http://x', 'query', 'id')
    assert r['verified'] is True


def test_proof_verifier_xss_reflected():
    def fake_inject(url, s, p, payload):
        token = payload.split('>')[1].split('<')[0]
        return FakeResp(f'<div>{token}</div>')
    verifier = ProofVerifier(fake_inject)
    r = verifier.verify_reflected_xss('http://x', 'query', 'q')
    assert r['verified'] is True
