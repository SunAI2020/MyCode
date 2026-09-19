# -*- coding: utf-8 -*-
"""version_match 精确匹配单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor"))

from version_match import (
    split_affected_entry,
    split_affected_products,
    version_matches,
    canonical_product,
    product_name_matches,
    detect_product_key,
    cve_applies,
    parse_version_constraints,
    version_satisfies,
)


def test_split_affected_entry_vendor_product():
    # vendor:product（无版本）
    assert split_affected_entry("redis:redis") == ("redis", None)
    assert split_affected_entry("postgresql:postgresql_jdbc_driver") == ("postgresql_jdbc_driver", None)
    assert split_affected_entry("symantec:norton_antivirus") == ("norton_antivirus", None)


def test_split_affected_entry_product_version():
    # product:version
    assert split_affected_entry("PostgreSQL:9.6") == ("PostgreSQL", "9.6")
    assert split_affected_entry("Apache HTTP Server:2.2") == ("Apache HTTP Server", "2.2")


def test_split_affected_products():
    entries = split_affected_products("PostgreSQL:9.3,PostgreSQL:9.6,redis:redis")
    assert ("PostgreSQL", "9.3") in entries
    assert ("PostgreSQL", "9.6") in entries
    assert ("redis", None) in entries


def test_version_matches_prefix():
    assert version_matches("9.6.0", "9.6") is True
    assert version_matches("9.6.0", "9.5") is False
    assert version_matches("7.4.9", "") is True
    assert version_matches("10.3", "10") is True
    assert version_matches("2.2.15", "2.2") is True


def test_canonical_product():
    assert canonical_product("redis") == "redis"
    assert canonical_product("apache httpd") == "apache_http_server"
    assert canonical_product("Apache HTTP Server") == "apache_http_server"
    assert canonical_product("postgresql") == "postgresql"
    # 复合产品不应被误归一化
    assert canonical_product("postgresql_jdbc_driver") == "postgresql jdbc driver"
    assert canonical_product("Samba smbd") == "smb"


def test_product_name_matches_strict():
    assert product_name_matches("redis", "redis") is True
    assert product_name_matches("redis", "redistimeseries") is False
    assert product_name_matches("postgresql", "postgresql_jdbc_driver") is False
    assert product_name_matches("apache httpd", "Apache HTTP Server") is True
    assert product_name_matches("Samba smbd", "samba") is True


def test_detect_product_key_skips_generic():
    assert detect_product_key("", "http") is None
    assert detect_product_key("redis", "redis") == "redis"
    assert detect_product_key("", "msrpc") == "msrpc"


def test_cve_applies_product_version():
    cve = {"cve_id": "CVE-2019-9193",
           "affected_products": "PostgreSQL:10,PostgreSQL:11,PostgreSQL:9.6",
           "description": ""}
    verdict = cve_applies(cve, "postgresql", "9.6.0")
    assert verdict["confidence"] == "high"
    assert verdict["matched_by"] == "product+version"
    assert cve_applies(cve, "postgresql", "12.0") is None


def test_cve_applies_rejects_unrelated():
    cve = {"cve_id": "CVE-X", "affected_products": "broadcom:symantec_siteminder", "description": ""}
    assert cve_applies(cve, "msrpc", "") is None


def test_cve_applies_description_range():
    cve = {"cve_id": "CVE-2026-23479", "affected_products": "redis:redis",
           "description": "Redis ... in redis-server from 7.2.0 until 8.6.3 ... patched in 8.6.3."}
    assert cve_applies(cve, "redis", "7.4.9")["confidence"] == "medium"


def test_version_satisfies():
    cons = parse_version_constraints("from 7.2.0 until 8.6.3, patched in 8.6.3")
    assert version_satisfies("7.4.9", cons) is True
    assert version_satisfies("8.6.3", cons) is False
