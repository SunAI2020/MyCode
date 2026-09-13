# -*- coding: utf-8 -*-
"""web_scanner 模块单元测试 — 纯逻辑（不依赖网络）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_scanner import WebFingerprinter, DirectoryEnumerator, ZAPScanner, HTTPProber


class TestWebFingerprinter:
    def test_dedupe_keeps_highest_confidence(self):
        products = [
            {'product': 'WordPress', 'confidence': 'low', 'version': '', 'category': 'cms', 'evidence': 'a'},
            {'product': 'WordPress', 'confidence': 'high', 'version': '', 'category': 'cms', 'evidence': 'b'},
            {'product': 'nginx', 'confidence': 'high', 'version': '1.18', 'category': 'middleware', 'evidence': 'c'},
        ]
        result = WebFingerprinter.dedupe(products)
        by_name = {p['product']: p for p in result}
        assert len(result) == 2
        assert by_name['WordPress']['confidence'] == 'high'
        assert by_name['WordPress']['evidence'] == 'b'

    def test_dedupe_empty(self):
        assert WebFingerprinter.dedupe([]) == []

    def test_extract_title(self):
        fp = WebFingerprinter()
        body = '<html><head><title>  Test Page </title></head><body></body></html>'
        assert fp._extract_title(body) == 'Test Page'
        assert fp._extract_title('<html></html>') == ''

    def test_match_body_wordpress(self):
        fp = WebFingerprinter()
        products = []
        fp._match_body('<html>wp-content/uploads/x.jpg</html>', products)
        assert any(p['product'] == 'WordPress' for p in products)


class TestDirectoryEnumerator:
    def test_build_paths_includes_backup_variants(self):
        paths = DirectoryEnumerator.build_paths('admin')
        assert '/admin/' in paths
        assert '/admin' in paths
        assert '/admin.bak' in paths
        assert '/admin.sql' in paths
        assert '/admin.zip' in paths

    def test_classify_directory_200(self):
        r = DirectoryEnumerator.classify('/admin/', 200)
        assert r is not None
        assert r['type'] == 'directory'
        assert r['severity'] == 'MEDIUM'

    def test_classify_backup_200_high(self):
        r = DirectoryEnumerator.classify('/db.sql', 200)
        assert r is not None
        assert r['type'] == 'backup_file'
        assert r['severity'] == 'HIGH'

    def test_classify_404_none(self):
        assert DirectoryEnumerator.classify('/nope/', 404) is None

    def test_classify_403_medium(self):
        r = DirectoryEnumerator.classify('/config', 403)
        assert r is not None
        assert r['type'] == 'directory'


class TestZAPScanner:
    def test_severity_map(self):
        zap = ZAPScanner()
        assert zap._map_alert({'alert': 'X', 'risk': 'High'})['severity'] == 'HIGH'
        assert zap._map_alert({'alert': 'X', 'risk': 'Informational'})['severity'] == 'INFO'
        assert zap._map_alert({'alert': 'X', 'risk': 'Unknown'})['severity'] == 'INFO'

    def test_map_alert_truncates(self):
        zap = ZAPScanner()
        a = zap._map_alert({'alert': 'A', 'risk': 'Medium', 'description': 'd' * 1000})
        assert len(a['description']) <= 500


class TestHTTPProber:
    def test_high_risk_paths_constant(self):
        assert any(p[0] == '/.env' for p in HTTPProber.HIGH_RISK_PATHS)
        assert any(p[0] == '/.git/config' for p in HTTPProber.HIGH_RISK_PATHS)
