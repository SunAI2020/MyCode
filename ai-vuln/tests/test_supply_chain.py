# -*- coding: utf-8 -*-
"""supply_chain 模块单元测试 — 解析 + 版本匹配（纯逻辑，不依赖 DB）"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supply_chain import (
    parse_requirements, parse_package_json, parse_go_mod, parse_pom_xml,
    parse_cargo_toml, parse_gemfile, parse_pipfile, parse_poetry_lock,
    _version_matches_spec, _version_in_affected, match_dependencies_to_cves,
)


# ===== 依赖清单解析 =====

def test_parse_requirements():
    content = "# comment\nrequests==2.25.1\nflask>=2.0  ; python_version>='3.6'\ndjango\n"
    deps = parse_requirements(content)
    assert {'name': 'requests', 'version': '2.25.1', 'ecosystem': 'pypi'} in deps
    assert {'name': 'flask', 'version': '2.0', 'ecosystem': 'pypi'} in deps
    assert {'name': 'django', 'version': '', 'ecosystem': 'pypi'} in deps


def test_parse_package_json():
    content = ('{"dependencies": {"lodash": "^4.17.20", "express": "4.17.1"},'
               ' "devDependencies": {"jest": "~26.0.0"}}')
    deps = parse_package_json(content)
    assert {'name': 'lodash', 'version': '4.17.20', 'ecosystem': 'npm'} in deps
    assert {'name': 'express', 'version': '4.17.1', 'ecosystem': 'npm'} in deps
    assert {'name': 'jest', 'version': '26.0.0', 'ecosystem': 'npm'} in deps


def test_parse_go_mod():
    content = "require (\n\tgithub.com/gin-gonic/gin v1.7.0\n\tgithub.com/pkg/errors v0.9.1\n)\n"
    deps = parse_go_mod(content)
    assert {'name': 'github.com/gin-gonic/gin', 'version': '1.7.0', 'ecosystem': 'go'} in deps


def test_parse_pom_xml():
    content = ('<project><properties><spring.version>5.3.9</spring.version></properties>'
               '<dependencies><dependency><groupId>org.springframework</groupId>'
               '<artifactId>spring-core</artifactId><version>${spring.version}</version>'
               '</dependency></dependencies></project>')
    deps = parse_pom_xml(content)
    assert {'name': 'org.springframework:spring-core', 'version': '5.3.9', 'ecosystem': 'maven'} in deps


def test_parse_cargo_and_gemfile_and_pipfile():
    cargo = parse_cargo_toml('[dependencies]\nserde = "1.0.130"\n')
    assert {'name': 'serde', 'version': '1.0.130', 'ecosystem': 'cargo'} in cargo
    gem = parse_gemfile("gem 'rails', '~> 6.1.4'\n")
    assert {'name': 'rails', 'version': '6.1.4', 'ecosystem': 'rubygems'} in gem
    pip = parse_pipfile('[packages]\nrequests = "==2.26.0"\n')
    assert {'name': 'requests', 'version': '==2.26.0', 'ecosystem': 'pypi'} in pip


# ===== 版本匹配 =====

def test_version_matches_exact():
    assert _version_matches_spec((1, 2, 3), '1.2.3') is True
    assert _version_matches_spec((1, 2, 3), '1.2.4') is False


def test_version_matches_lt():
    assert _version_matches_spec((1, 0, 0), '< 2.0') is True
    assert _version_matches_spec((2, 0, 0), '< 2.0') is False


def test_version_matches_lte():
    assert _version_matches_spec((2, 0, 0), '<= 2.0') is True
    assert _version_matches_spec((2, 0, 1), '<= 2.0') is False


def test_version_matches_range():
    assert _version_matches_spec((1, 5, 0), '1.0 through 2.0') is True
    assert _version_matches_spec((3, 0, 0), '1.0 through 2.0') is False


def test_version_matches_unparseable_conservative():
    # 无法解析的约束 → 保守 True（不排除）
    assert _version_matches_spec((1, 0, 0), 'weird-version-spec') is True
    assert _version_matches_spec((1, 0, 0), 'all versions') is True


def test_version_in_affected_positive():
    assert _version_in_affected('1.1.1', 'OpenSSL:1.1.1, Other:2.0', 'openssl') is True


def test_version_in_affected_negative():
    assert _version_in_affected('3.0.5', 'OpenSSL:< 2.0', 'openssl') is False


def test_version_in_affected_no_version_conservative():
    assert _version_in_affected('', 'OpenSSL:1.1.1', 'openssl') is True


def test_version_in_affected_name_not_matched_conservative():
    assert _version_in_affected('1.0.0', 'TotallyOther:1.0', 'openssl') is True


# ===== CVE 匹配 =====

class FakeCVEDB:
    def __init__(self, results):
        self._results = results
        self.closed = False

    def search_cve_by_product(self, name, limit=100):
        return self._results.get(name, [])

    def close(self):
        self.closed = True


def test_match_dependencies_to_cves():
    db = FakeCVEDB({
        'openssl': [
            {'cve_id': 'CVE-2021-3449', 'name': 'OpenSSL DoS', 'cvss_score': 7.5,
             'severity': 'HIGH', 'affected_products': 'OpenSSL:<1.1.1',
             'description': 'DoS in OpenSSL', 'references_url': 'https://example.com'},
        ],
    })
    deps = [{'name': 'openssl', 'version': '1.0.2', 'file': '/tmp/req.txt', 'ecosystem': 'pypi'}]
    findings = match_dependencies_to_cves(deps, db)
    assert len(findings) == 1
    f = findings[0]
    # 字段对齐 audit finding 结构
    for key in ('file', 'line', 'dimension', 'code', 'category', 'severity', 'problem', 'recommendation'):
        assert key in f
    assert f['dimension'] == 'supply_chain'
    assert f['category'] == '已知CVE依赖'
    assert f['severity'] == 'HIGH'
    assert f['evidence']['cve_id'] == 'CVE-2021-3449'
    assert f['evidence']['cvss_score'] == 7.5


def test_match_dependencies_excludes_patched_version():
    db = FakeCVEDB({
        'openssl': [
            {'cve_id': 'CVE-2021-3449', 'name': 'OpenSSL DoS', 'cvss_score': 7.5,
             'severity': 'HIGH', 'affected_products': 'OpenSSL:<1.1.1',
             'description': 'x', 'references_url': ''},
        ],
    })
    # 3.0.5 不在 <1.1.1 范围内 → 排除
    deps = [{'name': 'openssl', 'version': '3.0.5', 'file': 'req.txt'}]
    assert match_dependencies_to_cves(deps, db) == []


# ===== 字母后缀版本排序（修复后）=====

def test_lettered_suffix_ordering():
    # <1.1.1k 不应排除 1.1.1（1.1.1 在 1.1.1k 之前，受影响）
    assert _version_in_affected('1.1.1', 'OpenSSL:<1.1.1k', 'openssl') is True
    # 1.1.1k 已修复（等于补丁版本），不在 <1.1.1k 范围
    assert _version_in_affected('1.1.1k', 'OpenSSL:<1.1.1k', 'openssl') is False


# ===== Layer 2：恶意依赖检测 =====

def test_detect_typosquatting():
    from supply_chain import detect_typosquatting
    assert detect_typosquatting({'name': 'requsts', 'ecosystem': 'pypi'}) == 'requests'
    assert detect_typosquatting({'name': 'requests', 'ecosystem': 'pypi'}) is None


def test_detect_dependency_confusion():
    from supply_chain import detect_dependency_confusion
    # 无版本 + 非知名包 → 疑似私有包依赖混淆
    assert detect_dependency_confusion({'name': 'my-internal-lib', 'version': '', 'ecosystem': 'pypi'}) is True
    # 知名包无版本 → 不误报
    assert detect_dependency_confusion({'name': 'requests', 'version': '', 'ecosystem': 'pypi'}) is False
    # 有版本 → 不是依赖混淆
    assert detect_dependency_confusion({'name': 'my-internal-lib', 'version': '1.0', 'ecosystem': 'pypi'}) is False


def test_detect_suspicious_dependencies():
    from supply_chain import detect_suspicious_dependencies
    deps = [
        {'name': 'requsts', 'version': '2.0', 'ecosystem': 'pypi', 'file': 'req.txt', 'line': 1},
        {'name': 'my-internal-lib', 'version': '', 'ecosystem': 'pypi', 'file': 'req.txt', 'line': 2},
    ]
    findings = detect_suspicious_dependencies(deps)
    assert len(findings) == 2
    types = {f['evidence']['suspicious_type'] for f in findings}
    assert types == {'typosquatting', 'dependency_confusion'}
    assert all(f['dimension'] == 'supply_chain' for f in findings)
    assert all(f['category'] == '疑似恶意依赖' for f in findings)
