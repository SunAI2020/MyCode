# -*- coding: utf-8 -*-
"""代码审计发现相似度去重测试"""
from audit_dedup import AuditDeduplicator, similarity, fingerprint


def _f(file='a.py', line=10, dimension='function', category='函数过长',
       severity='MEDIUM', code='def foo():', **kw):
    d = {'file': file, 'line': line, 'dimension': dimension, 'category': category,
         'severity': severity, 'code': code, 'problem': 'p', 'recommendation': 'r'}
    d.update(kw)
    return d


def test_same_line_similar():
    assert similarity(_f(line=10), _f(line=10)) == 1.0


def test_different_file_not_similar():
    assert similarity(_f(file='a.py'), _f(file='b.py')) == 0.0


def test_different_category_not_similar():
    assert similarity(_f(category='函数过长'), _f(category='循环嵌套')) == 0.0


def test_dedup_keeps_one():
    d = AuditDeduplicator()
    r = d.deduplicate([_f(), _f(), _f(category='循环嵌套')])
    assert len(r['unique']) == 2
    assert len(r['duplicates']) == 1


def test_dedup_keeps_higher_severity():
    d = AuditDeduplicator()
    r = d.deduplicate([_f(severity='LOW'), _f(severity='HIGH')])
    assert len(r['unique']) == 1
    assert r['unique'][0]['severity'] == 'HIGH'
