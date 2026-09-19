# -*- coding: utf-8 -*-
"""漏洞预过滤规则引擎单测 — _parse_version / _parse_affected_range / 产品矛盾判断"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_scan_enhancer import (
    AIScanEnhancer,
    _parse_version,
    _parse_affected_range,
    _normalize_product,
)


# ============ _parse_version ============

def test_parse_version_pads_to_three_segments():
    assert _parse_version('1.2') == (1, 2, 0)
    assert _parse_version('1') == (1, 0, 0)
    assert _parse_version('1.2.3') == (1, 2, 3)
    assert _parse_version('1.2.3.4') == (1, 2, 3, 4)


def test_parse_version_strips_prerelease():
    assert _parse_version('1.2.3-p1') == (1, 2, 3)
    assert _parse_version('1.2.3-rc1') == (1, 2, 3)
    assert _parse_version('1.2.3+deb10u1') == (1, 2, 3)


def test_parse_version_invalid_raises():
    with pytest.raises(ValueError):
        _parse_version('abc')
    with pytest.raises(ValueError):
        _parse_version('')


# ============ _parse_affected_range ============

def test_affected_range_before_exclusive():
    min_ver, min_incl, max_ver, max_incl = _parse_affected_range(
        'vulnerability in Apache HTTP Server before 2.4.50')
    assert max_ver == (2, 4, 50)
    assert max_incl is False
    assert min_ver is None


def test_affected_range_le_inclusive():
    min_ver, min_incl, max_ver, max_incl = _parse_affected_range('versions <= 2.4.49')
    assert max_ver == (2, 4, 49)
    assert max_incl is True


def test_affected_range_ge_inclusive():
    min_ver, min_incl, max_ver, max_incl = _parse_affected_range('versions >= 2.4.49')
    assert min_ver == (2, 4, 49)
    assert min_incl is True
    assert max_ver is None


def test_affected_range_through():
    min_ver, min_incl, max_ver, max_incl = _parse_affected_range('2.4.49 through 2.4.55')
    assert min_ver == (2, 4, 49)
    assert min_incl is True
    assert max_ver == (2, 4, 55)
    assert max_incl is True


def test_affected_range_ge_and_lt():
    min_ver, min_incl, max_ver, max_incl = _parse_affected_range('>= 2.4.49 and < 2.4.55')
    assert min_ver == (2, 4, 49)
    assert min_incl is True
    assert max_ver == (2, 4, 55)
    assert max_incl is False


# ============ _normalize_product ============

def test_normalize_product_known():
    assert _normalize_product('OpenSSH 8.2') == {'openssh'}
    assert _normalize_product('Apache HTTP Server') == {'apache_httpd'}


def test_normalize_product_unknown():
    assert _normalize_product('某个未知产品') is None
    assert _normalize_product('') is None
    assert _normalize_product(None) is None


def test_normalize_product_word_boundary():
    # 'ssh' 不应命中 'openssh'
    assert _normalize_product('openssh') == {'openssh'}


# ============ _pre_filter_version（静态方法，直接调用） ============

def test_pre_filter_version_above_max_excluded():
    vuln = {
        'service': 'http', 'product': 'Apache', 'version': 'Apache 2.4.52',
        'description': 'vulnerability in Apache HTTP Server before 2.4.50',
        'affected_versions': 'Apache HTTP Server',
    }
    should_exclude, reason = AIScanEnhancer._pre_filter_version(vuln)
    assert should_exclude is True
    assert '高于受影响范围上限' in reason


def test_pre_filter_version_below_min_excluded():
    vuln = {
        'service': 'redis', 'product': 'Redis', 'version': 'Redis 5.0.0',
        'description': 'affects Redis versions >= 6.0.0',
        'affected_versions': 'Redis',
    }
    should_exclude, reason = AIScanEnhancer._pre_filter_version(vuln)
    assert should_exclude is True
    assert '低于受影响范围下限' in reason


def test_pre_filter_version_in_range_kept():
    vuln = {
        'service': 'redis', 'product': 'Redis', 'version': 'Redis 6.2.0',
        'description': 'affects Redis versions >= 6.0.0',
        'affected_versions': 'Redis',
    }
    should_exclude, reason = AIScanEnhancer._pre_filter_version(vuln)
    assert should_exclude is False


def test_pre_filter_product_mismatch_excluded():
    vuln = {
        'service': 'ssh', 'product': 'OpenSSH', 'version': 'OpenSSH 8.2',
        'description': 'Vulnerability in Apache HTTP Server allows remote code execution',
        'affected_versions': 'Apache HTTP Server 2.4.x',
    }
    should_exclude, reason = AIScanEnhancer._pre_filter_version(vuln)
    assert should_exclude is True
    assert '不匹配' in reason


def test_pre_filter_product_match_kept():
    vuln = {
        'service': 'http', 'product': 'Apache', 'version': 'Apache 2.4.49',
        'description': 'Path traversal in Apache HTTP Server 2.4.49',
        'affected_versions': 'Apache 2.4.49',
    }
    should_exclude, reason = AIScanEnhancer._pre_filter_version(vuln)
    assert should_exclude is False


def test_pre_filter_unknown_product_kept():
    # 任何一侧无法归一化 → 保守保留
    vuln = {
        'service': 'ssh', 'product': '', 'version': '',
        'description': 'a vulnerability',
        'affected_versions': '某个未知产品',
    }
    should_exclude, reason = AIScanEnhancer._pre_filter_version(vuln)
    assert should_exclude is False


# ============ verify_vulnerabilities 回归 ============

def test_verify_vulnerabilities_prefilter_skips_ai():
    enhancer = AIScanEnhancer()
    vulns = [{
        'host': 'h', 'port': 22, 'service': 'ssh', 'product': 'OpenSSH',
        'version': 'OpenSSH 8.2', 'cve_id': 'CVE-2021-0001',
        'description': 'Vulnerability in Apache HTTP Server before 2.4.50',
        'affected_versions': 'Apache HTTP Server', 'severity': 'HIGH',
    }]
    result = enhancer.verify_vulnerabilities(vulns, scan_context='t')

    assert result['stats']['pre_filtered'] == 1
    assert result['stats']['ai_verified'] == 0
    assert result['excluded'][0].get('pre_filtered') is True
    assert result['excluded'][0].get('excluded_reason', '').startswith('版本预过滤')
