# -*- coding: utf-8 -*-
"""weak_password_scanner 模块单元测试 — 纯逻辑（不依赖网络）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from weak_password_scanner import (
    WeakPasswordScanner, HTTPBasicAuthHandler, FTPHandler, SSHHandler,
    BUILTIN_CREDENTIALS, SUPPORTED_PROTOCOLS,
)


class TestProtocolMapping:
    def test_map_protocol(self):
        assert WeakPasswordScanner.map_protocol('http') == 'http'
        assert WeakPasswordScanner.map_protocol('https') == 'https'
        assert WeakPasswordScanner.map_protocol('ftp') == 'ftp'
        assert WeakPasswordScanner.map_protocol('ssh') == 'ssh'
        assert WeakPasswordScanner.map_protocol('mysql') == 'mysql'
        assert WeakPasswordScanner.map_protocol('postgresql') == 'postgresql'

    def test_is_supported(self):
        s = WeakPasswordScanner()
        assert s.is_supported('http')
        assert s.is_supported('ftp')
        assert s.is_supported('mysql')
        assert not s.is_supported('mssql')


class TestCredentials:
    def test_builtin_credentials_nonempty(self):
        assert len(BUILTIN_CREDENTIALS) > 0
        assert all('username' in c and 'password' in c for c in BUILTIN_CREDENTIALS)

    def test_get_credentials_fallback_without_db(self):
        s = WeakPasswordScanner(db=None)
        creds = s.get_credentials('ftp')
        assert creds == BUILTIN_CREDENTIALS

    def test_get_credentials_from_db(self, intel_db):
        s = WeakPasswordScanner(db=intel_db)
        creds = s.get_credentials('generic')
        assert len(creds) > 0
        assert 'admin' in [c['username'] for c in creds]


class TestUnsupportedProtocol:
    def test_scan_unsupported_returns_reason(self):
        s = WeakPasswordScanner(db=None)
        r = s.scan('127.0.0.1', 3306, 'mssql')
        assert r['service_supported'] is False
        assert '不支持' in r['reason']
        assert r['found'] == []
