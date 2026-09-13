# -*- coding: utf-8 -*-
"""漏洞相似度去重测试"""
from vuln_dedup import VulnDeduplicator, similarity, fingerprint


def _v(cve, host='1.2.3.4', service='http', version='2.4.0', **kw):
    d = {'cve_id': cve, 'host': host, 'service': service, 'version': version}
    d.update(kw)
    return d


def test_same_fingerprint_similar():
    a = _v('CVE-2020-1')
    b = _v('CVE-2020-1')
    assert similarity(a, b) == 1.0


def test_different_host_not_similar():
    a = _v('CVE-2020-1', host='1.2.3.4')
    b = _v('CVE-2020-1', host='5.6.7.8')
    assert similarity(a, b) == 0.0


def test_different_service_not_similar():
    a = _v('CVE-2020-1', service='http')
    b = _v('CVE-2020-1', service='ssh')
    assert similarity(a, b) == 0.0


def test_dedup_keeps_one():
    d = VulnDeduplicator()
    r = d.deduplicate([_v('CVE-1'), _v('CVE-1'), _v('CVE-2')])
    assert len(r['unique']) == 2
    assert len(r['duplicates']) == 1


def test_dedup_keeps_higher_priority():
    d = VulnDeduplicator()
    low = _v('CVE-1', risk_score=30)
    high = _v('CVE-1', risk_score=90)
    r = d.deduplicate([low, high])
    assert len(r['unique']) == 1
    assert r['unique'][0]['risk_score'] == 90


def test_missing_version_still_similar():
    a = _v('CVE-1', version='')
    b = _v('CVE-1', version='')
    assert similarity(a, b) == 0.9
