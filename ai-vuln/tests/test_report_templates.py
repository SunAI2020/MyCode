# -*- coding: utf-8 -*-
"""报告模板测试"""
from report_templates import render_report, TEMPLATE_DEFS


def _scan():
    return {
        'target': '10.0.0.1',
        'summary': {'total': 5, 'high_critical': 2},
        'vulnerabilities': [
            {'cve_id': 'CVE-1', 'severity': 'CRITICAL'},
            {'cve_id': 'CVE-2', 'severity': 'HIGH'},
            {'cve_id': 'CVE-3', 'severity': 'MEDIUM'},
            {'cve_id': 'CVE-4', 'severity': 'LOW'},
        ],
    }


def test_five_templates_defined():
    assert set(TEMPLATE_DEFS.keys()) == {'standard', 'compliance', 'high_risk', 'executive', 'technical'}


def test_render_all_templates():
    for name in TEMPLATE_DEFS:
        r = render_report(_scan(), name)
        assert r['title']
        assert r['template'] == name


def test_high_risk_filters():
    r = render_report(_scan(), 'high_risk')
    sevs = {v['severity'] for v in r['vulns']}
    assert sevs == {'CRITICAL', 'HIGH'}


def test_standard_keeps_all():
    r = render_report(_scan(), 'standard')
    assert len(r['vulns']) == 4


def test_invalid_template_falls_back():
    r = render_report(_scan(), 'nope')
    assert r['template'] == 'standard'


def test_sorted_by_severity():
    r = render_report(_scan(), 'standard')
    sevs = [v['severity'] for v in r['vulns']]
    assert sevs[0] == 'CRITICAL'
