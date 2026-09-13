# -*- coding: utf-8 -*-
"""176号合规标准（mps176）专项测试 — 条款目录与评估冒烟"""
from compliance_engine import ComplianceEngine, EvidenceBundle, load_catalog

EXPECTED_DOMAINS = {
    '联网备案管理', '安全管理制度', '日志留存', '等级保护义务',
    '关键信息基础设施保护', '网络安全技术防护', '公共信息内容安全',
    '算法安全', '数据安全防护', '个人信息保护', '协助义务',
    '风险评估与管控', '应急与事件处置', '迎检配合与整改',
}


def test_catalog_loads():
    cat = load_catalog('mps176')
    assert cat['standard'] == 'mps176'
    assert '公安部令第176号' in cat['standard_name']
    controls = cat['controls']
    assert len(controls) >= 40
    domains = {c.domain for c in controls}
    assert EXPECTED_DOMAINS <= domains


def test_hybrid_controls_use_registered_checks():
    from compliance_checks import CHECK_REGISTRY
    for c in load_catalog('mps176')['controls']:
        if c.mode == 'hybrid':
            assert c.check in CHECK_REGISTRY, f'{c.id} 引用了未注册评估器 {c.check}'


def test_evaluate_smoke():
    eng = ComplianceEngine('mps176')
    agg = eng.evaluate(EvidenceBundle(target='10.0.0.1'), answers={}, level='ALL')
    assert len(agg['results']) == len(eng.controls_for_level('ALL'))
    # 全未填报且无技术证据时，无可计分条款，合规率为 None
    assert agg['compliance_rate'] is None
    assert agg['standard'] == 'mps176'


def test_report_generates_with_expected_prefix(tmp_path):
    """176号检查完成后自动保存，验证报告落盘命名与 COMPLIANCE_REPORT_NAMES 前缀一致。"""
    import os
    from compliance_report import generate_compliance_report
    eng = ComplianceEngine('mps176')
    agg = eng.evaluate(EvidenceBundle(target='10.0.0.1'), answers={}, level='ALL')
    prefix = '176号监督检查迎检自评报告'
    path = generate_compliance_report(agg, str(tmp_path), title=prefix, filename_prefix=prefix)
    assert os.path.isfile(path)
    assert os.path.basename(path).startswith(prefix)
    assert path.endswith('.html')
