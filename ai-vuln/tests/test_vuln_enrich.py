# -*- coding: utf-8 -*-
"""漏洞 evidence/remediation 结构化富化测试"""
import json

from vuln_enrich import (
    SERVICE_REMEDIATION, build_evidence, build_remediation,
    enrich_vulnerabilities, evidence_dict, remediation_dict,
)


def _v(cve='CVE-2020-1', service='http', **kw):
    d = {
        'host': '1.2.3.4', 'port': 80, 'protocol': 'tcp',
        'service': service, 'version': 'Apache/2.4.49', 'product': 'Apache',
        'cve_id': cve, 'cvss_score': 7.5, 'severity': 'HIGH',
        'kev': False, 'references_url': 'https://example.com/advisory',
    }
    d.update(kw)
    return d


def test_build_evidence_structure():
    ev = build_evidence(_v())
    for key in ('host', 'port', 'protocol', 'service', 'version', 'product',
                'cve_id', 'cvss_score', 'severity', 'kev', 'references', 'matched_by', 'summary'):
        assert key in ev
    assert ev['service'] == 'http'
    assert ev['port'] == 80
    assert ev['cve_id'] == 'CVE-2020-1'
    assert 'CVE-2020-1' in ev['summary']


def test_build_remediation_ai_priority():
    v = _v(ai_remediation='升级到 2.4.50 并重启')
    rm = build_remediation(v)
    assert rm['source'] == 'ai'
    assert rm['summary'] == '升级到 2.4.50 并重启'
    assert rm['steps'] == ['升级到 2.4.50 并重启']


def test_build_remediation_rule():
    rm = build_remediation(_v(service='redis'))
    assert rm['source'] == 'rule'
    assert rm['steps'] == SERVICE_REMEDIATION['redis']


def test_build_remediation_generic_fallback():
    rm = build_remediation(_v(service='some-unknown-svc'))
    assert rm['source'] == 'generic'
    assert rm['steps']


def test_enrich_adds_fields():
    v = _v()
    out = enrich_vulnerabilities([v])
    assert isinstance(v['evidence'], dict)
    assert isinstance(v['remediation'], dict)
    assert len(out) == 1


def test_enrich_recompute_remediation_after_ai():
    v = _v()
    enrich_vulnerabilities([v])
    assert v['remediation']['source'] == 'rule'
    # AI 核验后追加 ai_remediation，重跑富化应刷新为 ai 来源
    v['ai_remediation'] = '升级并重启服务'
    enrich_vulnerabilities([v])
    assert v['remediation']['source'] == 'ai'
    # evidence 不应被重复覆盖
    assert v['evidence']['service'] == 'http'


def test_evidence_dict_normalizes_json_string():
    v = _v()
    enrich_vulnerabilities([v])
    # 模拟 DB 持久化后字段变为 JSON 字符串
    v['evidence'] = json.dumps(v['evidence'], ensure_ascii=False)
    v['remediation'] = json.dumps(v['remediation'], ensure_ascii=False)
    v.pop('ai_remediation', None)
    ev = evidence_dict(v)
    assert isinstance(ev, dict)
    assert ev['service'] == 'http'
    assert isinstance(remediation_dict(v), dict)
