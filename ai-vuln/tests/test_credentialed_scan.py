# -*- coding: utf-8 -*-
"""credentialed_scan 模块单元测试 — 纯逻辑（不依赖网络/paramiko）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from credentialed_scan import (
    build_package_query, parse_package_output, CredentialedScanner,
    PACKAGE_QUERY_COMMANDS, PARAMIKO_AVAILABLE,
)


def test_build_package_query_known_types():
    assert 'rpm -qa' in build_package_query('linux-rpm')
    assert 'dpkg-query' in build_package_query('linux-deb')
    assert 'Uninstall' in build_package_query('windows')
    assert 'DisplayName' in build_package_query('windows')


def test_build_package_query_unknown_fallback():
    assert build_package_query('macos') == PACKAGE_QUERY_COMMANDS['linux-rpm']


def test_parse_rpm_output():
    raw = "openssl 1.1.1k-1.el8\nbash 4.4.20-1.el8\n"
    pkgs = parse_package_output('linux-rpm', raw)
    assert len(pkgs) == 2
    assert pkgs[0] == {'product': 'openssl', 'version': '1.1.1k-1.el8'}


def test_parse_dpkg_output():
    raw = "openssl 1.1.1-1ubuntu2.1~18.04.9\nlibc6 2.27-3ubuntu1.6\n"
    pkgs = parse_package_output('linux-deb', raw)
    assert pkgs[1] == {'product': 'libc6', 'version': '2.27-3ubuntu1.6'}


def test_parse_windows_output():
    raw = "Google Chrome 120.0.6099.130\n7-Zip 23.01\n"
    pkgs = parse_package_output('windows', raw)
    assert len(pkgs) == 2
    assert pkgs[0] == {'product': 'Google Chrome', 'version': '120.0.6099.130'}


def test_parse_empty_and_garbage():
    assert parse_package_output('linux-rpm', '') == []
    assert parse_package_output('linux-rpm', None) == []
    # 单列无版本行应被跳过
    assert parse_package_output('linux-rpm', "singlecolumn\n") == []


def test_enumerate_without_paramiko_degrades_gracefully():
    r = CredentialedScanner().enumerate_packages('192.168.1.1', 'root', password='x')
    if not PARAMIKO_AVAILABLE:
        assert r['status'] == 'unsupported'
        assert r['packages'] == []
    else:
        # paramiko 可用时不作真实连接断言，仅保证返回结构合法
        assert r['status'] in ('ok', 'error', 'unsupported')
        assert isinstance(r['packages'], list)
