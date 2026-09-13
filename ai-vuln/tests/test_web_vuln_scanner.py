# -*- coding: utf-8 -*-
"""web_vuln_scanner 模块单元测试 — 纯逻辑（不依赖网络）"""
from urllib.parse import urlparse

from web_vuln_scanner import (
    WebVulnScanner,
    SafeHTTPClient,
    Surface,
    extract_surfaces,
    inject,
    _SEVERITY_MAP,
)


class TestSeverityNormalization:
    def test_severity_map(self):
        assert _SEVERITY_MAP['critical'] == 'CRITICAL'
        assert _SEVERITY_MAP['high'] == 'HIGH'
        assert _SEVERITY_MAP['medium'] == 'MEDIUM'
        assert _SEVERITY_MAP['low'] == 'LOW'
        assert _SEVERITY_MAP['info'] == 'INFO'

    def test_normalize_finding_structure(self):
        raw = [{
            'type': 'SQL Injection', 'severity': 'critical', 'url': 'http://x/a',
            'parameter': 'id', 'payload': "' OR 1=1",
            'evidence': 'SQL error', 'description': 'SQLi', 'remediation': 'fix',
        }]
        out = WebVulnScanner._normalize(raw)
        assert len(out) == 1
        f = out[0]
        assert f['category'] == 'web_vuln'
        assert f['scan_type'] == 'web_vuln'
        assert f['title'] == 'SQL Injection'
        assert f['severity'] == 'CRITICAL'
        assert f['detail'] == 'SQLi'
        assert f['parameter'] == 'id'
        assert f['payload'] == "' OR 1=1"


class TestSurfaces:
    def test_query_and_path_extraction(self):
        ctx = {'json_body': {'user': 'a', 'flag': True}, 'cookies': {'sid': '1'}}
        surfaces = extract_surfaces('http://h/page/123?q=1&x=a', ctx)
        query = dict(surfaces[Surface.QUERY])
        assert query['q'] == '1'
        assert query['x'] == 'a'
        assert '123' in [name for name, _ in surfaces[Surface.PATH_SEGMENT]]
        json_body = dict(surfaces[Surface.JSON_BODY])
        assert json_body['user'] == 'a'
        cookie = dict(surfaces[Surface.COOKIE])
        assert cookie['sid'] == '1'

    def test_dedupe(self):
        surfaces = extract_surfaces('http://h/?a=1&a=1', {})
        names = [n for n, _ in surfaces[Surface.QUERY]]
        assert names.count('a') == 1


class TestFormExtraction:
    def test_extract_post_form(self):
        html = ('<form method="POST" action="/login">'
                '<input name="user" value="a">'
                '<input type="password" name="pass"></form>')
        forms = WebVulnScanner._extract_forms(html, 'http://h/')
        assert len(forms) == 1
        f = forms[0]
        assert f['method'] == 'POST'
        assert f['action'] == '/login'
        names = [i['name'] for i in f['inputs']]
        assert names == ['user', 'pass']

    def test_extract_no_forms(self):
        assert WebVulnScanner._extract_forms('', 'http://h/') == []
        assert WebVulnScanner._extract_forms('<p>hello</p>', 'http://h/') == []

    def test_forms_feed_surfaces(self):
        forms = WebVulnScanner._extract_forms(
            '<form method="POST"><input name="q" value="1"></form>', 'http://h/')
        surf = extract_surfaces('http://h/page', {'forms': forms})
        assert dict(surf[Surface.FORM_POST]) == {'q': '1'}


class TestPayloads:
    def test_default_payloads_non_empty(self):
        for key in ('sql_injection', 'xss', 'command_injection'):
            assert WebVulnScanner.DEFAULT_PAYLOADS[key], key
        assert WebVulnScanner.DEFAULT_PAYLOADS['xxe']


class TestScanner:
    def test_default_enabled_checks(self):
        s = WebVulnScanner()
        for key in ('sql_injection', 'xss', 'ssrf', 'jwt_deep', 'idor', 'nosql_injection',
                    'stored_xss', 'hpp_pollution', 'http_method_override',
                    'mass_assignment', 'prototype_pollution', 'host_header_deep',
                    'crlf_header_inject_deep', 'open_redirect_deep', 'api_bola_deep',
                    'email_injection', 'graphql_deep', 'cache_poisoning',
                    'cache_deception', 'php_webshell', 'sse_injection', 'race_condition'):
            assert key in s.enabled_checks, key
        assert len(s.enabled_checks) >= 44

    def test_enabled_checks_override(self):
        s = WebVulnScanner(enabled_checks=['xss', 'ssrf'])
        assert s.enabled_checks == ['xss', 'ssrf']


class TestNewChecksPureLogic:
    def test_hpp_infer_behavior(self):
        infer = WebVulnScanner._infer_hpp_behavior
        assert infer("aHPP_PROBE_42", "HPP_PROBE_42", "a", "HPP_PROBE_42") == "concatenation"
        assert infer('["a", "HPP_PROBE_42"]', "HPP_PROBE_42", "a", "HPP_PROBE_42") == "array"
        assert infer("HPP_PROBE_42", "HPP_PROBE_42", "a", "HPP_PROBE_42") == "last-wins"
        assert infer("a", "HPP_PROBE_42", "a", "HPP_PROBE_42") == "first-wins"

    def test_new_payload_constants_non_empty(self):
        assert WebVulnScanner._OVERRIDE_HEADERS
        assert WebVulnScanner._OVERRIDE_METHODS == ["DELETE", "PATCH", "PUT"]
        assert WebVulnScanner._MASS_ASSIGN_FIELDS
        assert WebVulnScanner._PROTO_POLLUTION_PAYLOADS
        assert WebVulnScanner._EMAIL_PAYLOADS
        assert WebVulnScanner._PHP_WRAPPER_PAYLOADS

    def test_mass_assign_hit(self):
        hit = WebVulnScanner._mass_assign_hit
        assert hit('{"role": "admin"}', 'role', 'admin')
        assert not hit('<p>hello</p>', 'role', 'admin')


class TestHTTPClientSurface:
    def test_methods_present(self):
        c = SafeHTTPClient()
        for m in ('get', 'post', 'head', 'options', 'delete', 'put', 'patch', 'request'):
            assert hasattr(c, m)

    def test_inject_requires_client(self):
        import pytest
        with pytest.raises(ValueError):
            inject('http://h/', {}, Surface.QUERY, 'a', 'b', http_client=None)
