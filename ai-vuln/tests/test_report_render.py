# -*- coding: utf-8 -*-
"""报告渲染层回归测试 — 证据/修复方案结构化渲染与 XSS 防护"""
from report_generator import (
    _safe_href, _render_ref_links, _render_evidence_html, _render_remediation_html,
)


def test_safe_href_allows_http_https():
    assert _safe_href('https://nvd.nist.gov/vuln/detail/CVE-2021-41773')
    assert _safe_href('http://example.com/x')
    assert not _safe_href('javascript:alert(1)')
    assert not _safe_href('data:text/html;base64,xxx')
    assert not _safe_href('file:///etc/passwd')
    assert not _safe_href('vbscript:msgbox(1)')


def test_safe_href_handles_non_string():
    assert not _safe_href(None)
    assert not _safe_href(12345)


def test_render_ref_links_escapes_dangerous_scheme():
    out = _render_ref_links(['https://nvd.nist.gov/x', 'javascript:alert(1)', 'data:text/html;x'])
    assert 'href="https://nvd.nist.gov/x"' in out
    assert '<a href="javascript' not in out
    assert '<a href="data:' not in out
    assert '<code>javascript:alert(1)</code>' in out
    assert '<code>data:text/html;x</code>' in out


def test_render_ref_links_escapes_html_chars():
    out = _render_ref_links(['https://x.com/?a=<script>'])
    assert '<script>' not in out


def test_render_evidence_no_xss():
    ev = {
        'summary': '命中 CVE-2021-41773',
        'service': 'http', 'port': 80, 'protocol': 'tcp',
        'references': ['javascript:alert(1)'],
    }
    out = _render_evidence_html(ev)
    assert 'javascript:alert(1)' in out
    assert '<a href="javascript' not in out


def test_render_remediation_structured():
    rm = {
        'summary': '升级到安全版本',
        'steps': ['步骤一', '步骤二'],
        'source': 'rule',
        'urgency': '紧急修复',
        'references': ['https://nvd.nist.gov/x'],
    }
    out = _render_remediation_html(rm)
    assert '修复方案' in out
    assert '规则库' in out  # 来源徽标
    assert '<li>步骤一</li>' in out
    assert '紧急修复' in out
    assert 'href="https://nvd.nist.gov/x"' in out
