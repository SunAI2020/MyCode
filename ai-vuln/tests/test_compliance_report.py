# -*- coding: utf-8 -*-
"""合规报告渲染测试 — 强制披露、转义、状态着色"""
import os
import pytest

from compliance_engine import (
    ComplianceEngine, EvidenceBundle,
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA,
    STATUS_UNFILLED, STATUS_INSUFFICIENT,
    AI_DOUBTED, AI_CONFLICT, AI_INCOMPLETE,
)
from compliance_report import (
    render_compliance_html, generate_compliance_report,
    STATUS_COLORS, AI_COLORS, _pct,
)


@pytest.fixture
def result():
    eng = ComplianceEngine('dengbao')
    return eng.evaluate(EvidenceBundle(target='10.0.0.1', scope_key='OA系统'),
                        answers={'DB-PE-01': {'status': STATUS_PASS, 'note': '已确认'},
                                 'DB-PE-02': {'status': STATUS_FAIL, 'note': '无门禁'}},
                        level='L3')


# ============================================================
# 基本结构
# ============================================================
def test_renders_full_document(result):
    html = render_compliance_html(result)
    assert html.startswith('<!DOCTYPE html>')
    assert '<meta charset="UTF-8">' in html
    assert html.rstrip().endswith('</html>')


def test_includes_standard_and_scope(result):
    html = render_compliance_html(result)
    assert 'GB/T 22239-2019' in html
    assert '10.0.0.1' in html
    assert 'OA系统' in html
    assert 'L3' in html


def test_every_control_rendered(result):
    html = render_compliance_html(result)
    for r in result['results']:
        assert r['control_id'] in html


def test_domain_table_present(result):
    html = render_compliance_html(result)
    assert '按安全层面统计' in html
    for domain in result['by_domain']:
        assert domain in html


def test_custom_title(result):
    assert '年度自查报告' in render_compliance_html(result, title='年度自查报告')


# ============================================================
# 强制披露
# ============================================================
def test_disclosure_states_not_a_certification(result):
    """必须写明不构成测评认证结论 —— 这条不允许被删掉"""
    html = render_compliance_html(result)
    assert '不构成等级保护测评、认证或第三方审计结论' in html
    assert '不能替代具备资质的测评机构' in html


def test_disclosure_reports_auto_ratio_and_completion(result):
    html = render_compliance_html(result)
    assert '由系统自动技术检查判定' in html
    assert '填报完成度' in html
    assert _pct(result['auto_ratio']) in html


def test_disclosure_explains_denominator(result):
    """必须说清哪些状态不计分"""
    html = render_compliance_html(result)
    assert '一律不计分' in html
    assert '不适用 / 未填报 / 证据不足' in html
    # 空证据下 hybrid 条款合并为『未填报』，须被点名说明未计入合规率
    assert '尚未填报，同样未计入合规率' in html


def test_disclosure_warns_insufficient_is_not_pass():
    """有『证据不足』时必须显式警告不得误读为符合"""
    fake = {
        'standard': 'dengbao', 'standard_name': '等保', 'level': 'L3',
        'counts': {'total': 2, STATUS_INSUFFICIENT: 1, STATUS_PASS: 1,
                   STATUS_PARTIAL: 0, STATUS_FAIL: 0, STATUS_NA: 0, STATUS_UNFILLED: 0},
        'ai_counts': {}, 'source_counts': {}, 'by_domain': {}, 'results': [],
        'compliance_rate': 1.0, 'score': 100, 'scored_total': 1,
        'auto_ratio': 0.5, 'questionnaire_completion': 1.0, 'questionnaire_total': 1,
    }
    html = render_compliance_html(fake)
    assert '请勿理解为『符合』' in html


def test_disclosure_counts_ai_problems():
    fake = {
        'standard': 'dengbao', 'standard_name': '等保', 'level': 'L3',
        'counts': {'total': 3, STATUS_PASS: 1, STATUS_FAIL: 1, STATUS_INSUFFICIENT: 1,
                   STATUS_PARTIAL: 0, STATUS_NA: 0, STATUS_UNFILLED: 0},
        'ai_counts': {AI_DOUBTED: 2, AI_CONFLICT: 1, AI_INCOMPLETE: 4},
        'source_counts': {}, 'by_domain': {}, 'results': [],
        'compliance_rate': 0.5, 'score': 50, 'scored_total': 2,
        'auto_ratio': 0.33, 'questionnaire_completion': 0.5, 'questionnaire_total': 2,
    }
    html = render_compliance_html(fake)
    assert '1 项</b>自评结论与扫描到的技术事实矛盾' in html
    assert '2 项</b>AI 认为填报依据不足' in html
    assert '4 项</b>AI 研判未完成' in html
    assert '未经过 AI 核验' in html


def test_no_ai_problems_omits_warnings():
    fake = {
        'standard': 'cii', 'standard_name': '关基', 'level': 'ALL',
        'counts': {'total': 1, STATUS_PASS: 1, STATUS_PARTIAL: 0, STATUS_FAIL: 0,
                   STATUS_NA: 0, STATUS_UNFILLED: 0, STATUS_INSUFFICIENT: 0},
        'ai_counts': {}, 'source_counts': {}, 'by_domain': {}, 'results': [],
        'compliance_rate': 1.0, 'score': 100, 'scored_total': 1,
        'auto_ratio': 1.0, 'questionnaire_completion': None, 'questionnaire_total': 0,
    }
    html = render_compliance_html(fake)
    assert 'AI 研判未完成' not in html
    assert '不构成等级保护测评' in html      # 免责声明始终在


# ============================================================
# 呈现细节
# ============================================================
def test_none_rate_shows_dash_not_zero():
    """无法计算合规率时显示『—』，不能显示 0% 误导读者"""
    assert _pct(None) == '—'
    assert _pct(0.5) == '50.0%'
    assert _pct('bad') == '—'


def test_none_rate_document_renders():
    fake = {
        'standard': 'dengbao', 'standard_name': '等保', 'level': 'L2',
        'counts': {'total': 1, STATUS_UNFILLED: 1, STATUS_PASS: 0, STATUS_PARTIAL: 0,
                   STATUS_FAIL: 0, STATUS_NA: 0, STATUS_INSUFFICIENT: 0},
        'ai_counts': {}, 'source_counts': {}, 'by_domain': {}, 'results': [],
        'compliance_rate': None, 'score': None, 'scored_total': 0,
        'auto_ratio': 0.0, 'questionnaire_completion': 0.0, 'questionnaire_total': 1,
    }
    html = render_compliance_html(fake)
    assert '—' in html


def test_status_colors_applied(result):
    html = render_compliance_html(result)
    assert STATUS_COLORS[STATUS_FAIL] in html
    assert STATUS_COLORS[STATUS_PASS] in html


def test_ai_status_badge_colored():
    fake = {
        'standard': 'dengbao', 'standard_name': '等保', 'level': 'L3',
        'counts': {'total': 1, STATUS_PASS: 1, STATUS_PARTIAL: 0, STATUS_FAIL: 0,
                   STATUS_NA: 0, STATUS_UNFILLED: 0, STATUS_INSUFFICIENT: 0},
        'ai_counts': {AI_DOUBTED: 1}, 'source_counts': {}, 'by_domain': {},
        'compliance_rate': 0.5, 'score': 50, 'scored_total': 1,
        'auto_ratio': 0.0, 'questionnaire_completion': 1.0, 'questionnaire_total': 1,
        'results': [{'control_id': 'X-1', 'domain': 'D', 'category': 'C', 'title': 'T',
                     'requirement': 'R', 'status': STATUS_PASS, 'verdict_source': 'ai_assisted',
                     'ai_status': AI_DOUBTED, 'ai_reasoning': '缺证据', 'detail': '',
                     '_weight': 1.0}],
    }
    html = render_compliance_html(fake)
    assert AI_COLORS[AI_DOUBTED] in html
    assert 'AI辅助' in html


def test_html_is_escaped():
    """条款文本里的尖括号必须被转义，不能注入到报告结构里"""
    fake = {
        'standard': 'dengbao', 'standard_name': '等保', 'level': 'L3',
        'counts': {'total': 1, STATUS_FAIL: 1, STATUS_PASS: 0, STATUS_PARTIAL: 0,
                   STATUS_NA: 0, STATUS_UNFILLED: 0, STATUS_INSUFFICIENT: 0},
        'ai_counts': {}, 'source_counts': {}, 'by_domain': {},
        'compliance_rate': 0.0, 'score': 0, 'scored_total': 1,
        'auto_ratio': 1.0, 'questionnaire_completion': None, 'questionnaire_total': 0,
        'target': '<script>alert(1)</script>',
        'results': [{'control_id': 'X-1', 'domain': 'D', 'category': 'C',
                     'title': '<img src=x onerror=alert(1)>', 'requirement': 'R',
                     'status': STATUS_FAIL, 'detail': 'a & b < c', '_weight': 1.0}],
    }
    html = render_compliance_html(fake)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html
    assert '<img src=x' not in html
    assert 'a &amp; b &lt; c' in html


def test_failures_sorted_first(result):
    html = render_compliance_html(result)
    body = html.split('条款判定明细')[1]
    # DB-PE-02 判为不符合，应排在判为符合的 DB-PE-01 之前
    assert body.index('DB-PE-02') < body.index('DB-PE-01')


def test_empty_results_does_not_crash():
    fake = {'standard': 'dengbao', 'standard_name': '等保', 'counts': {}, 'results': [],
            'by_domain': {}, 'ai_counts': {}, 'source_counts': {}}
    html = render_compliance_html(fake)
    assert '无条款结果' in html
    assert '无分层数据' in html


# ============================================================
# 落盘
# ============================================================
def test_generate_writes_file(result, tmp_path):
    path = generate_compliance_report(result, output_dir=str(tmp_path))
    assert os.path.isfile(path)
    assert os.path.basename(path).startswith('compliance_dengbao_')
    assert path.endswith('.html')
    with open(path, encoding='utf-8') as f:
        content = f.read()
    assert '不构成等级保护测评' in content
    assert len(content) > 5000


def test_generate_creates_missing_dir(result, tmp_path):
    target = tmp_path / 'nested' / 'reports'
    path = generate_compliance_report(result, output_dir=str(target))
    assert os.path.isfile(path)


def test_generate_custom_filename_and_title(result, tmp_path):
    path = generate_compliance_report(
        result, output_dir=str(tmp_path),
        title='等保合规检查报告', filename_prefix='等保合规检查报告')
    assert os.path.isfile(path)
    assert os.path.basename(path).startswith('等保合规检查报告_')
    assert path.endswith('.html')
    with open(path, encoding='utf-8') as f:
        content = f.read()
    assert '等保合规检查报告' in content
