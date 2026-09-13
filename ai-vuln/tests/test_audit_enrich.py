# -*- coding: utf-8 -*-
"""代码审计发现 evidence/remediation 结构化富化测试"""
import json

from audit_enrich import (
    build_evidence, build_remediation, enrich_audit_findings,
    evidence_dict, remediation_dict,
)


def _f(**kw):
    d = {'file': 'a.py', 'line': 10, 'dimension': 'function', 'category': '函数过长',
         'severity': 'MEDIUM', 'code': 'def foo():', 'problem': '职责过多',
         'recommendation': '拆分为小函数；提取重复逻辑', 'source': 'rule'}
    d.update(kw)
    return d


def test_build_evidence_fields():
    ev = build_evidence(_f())
    assert ev['file'] == 'a.py'
    assert ev['line'] == 10
    assert ev['dimension'] == '函数规范'
    assert ev['summary']


def test_build_remediation_source_rule():
    rm = build_remediation(_f())
    assert rm['source'] == 'rule'
    assert len(rm['steps']) >= 2  # 按分号拆分为多个步骤


def test_build_remediation_source_ai():
    rm = build_remediation(_f(ai_fix_suggestion='使用依赖注入打破循环'))
    assert rm['source'] == 'ai'
    assert rm['summary'] == '使用依赖注入打破循环'


def test_build_remediation_generic_fallback():
    rm = build_remediation(_f(recommendation='', source=''))
    assert rm['source'] == 'generic'


def test_enrich_audit_findings_adds_fields():
    f = _f()
    out = enrich_audit_findings([f])
    assert isinstance(out[0]['evidence'], dict)
    assert isinstance(out[0]['remediation'], dict)


def test_evidence_dict_normalizes_json_string():
    f = _f()
    enrich_audit_findings([f])
    f['evidence'] = json.dumps(f['evidence'], ensure_ascii=False)
    assert isinstance(evidence_dict(f), dict)
    assert isinstance(remediation_dict(f), dict)
