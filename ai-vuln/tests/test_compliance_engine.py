# -*- coding: utf-8 -*-
"""合规检查引擎测试 — 条款目录、计分、AI降级表、保守判定"""
import pytest

import compliance_checks
from compliance_checks import CHECK_REGISTRY
from compliance_engine import (
    ComplianceControl, ComplianceEngine, EvidenceBundle, build_evidence,
    load_catalog, available_standards, score_factor, severity_for,
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA,
    STATUS_UNFILLED, STATUS_INSUFFICIENT, ALL_STATUSES,
    AI_NOT_RUN, AI_ENDORSED, AI_DOUBTED, AI_CONFLICT, AI_INCOMPLETE,
    SOURCE_QUESTIONNAIRE, SOURCE_AI_ASSISTED,
    MODE_AUTO, MODE_QUESTIONNAIRE, MODE_HYBRID,
)

STANDARDS = ['dengbao', 'cii', 'data_security', 'mps176']
AI_STATUSES = [AI_NOT_RUN, AI_ENDORSED, AI_DOUBTED, AI_CONFLICT, AI_INCOMPLETE]


# ============================================================
# 条款目录
# ============================================================
def test_three_standards_available():
    assert set(STANDARDS).issubset(set(available_standards()))


@pytest.mark.parametrize('standard', STANDARDS)
def test_catalog_loads_with_enough_controls(standard):
    cat = load_catalog(standard)
    assert cat['standard'] == standard
    assert cat['standard_name']
    # 首期每标准至少 40 条
    assert len(cat['controls']) >= 40


@pytest.mark.parametrize('standard', STANDARDS)
def test_control_ids_unique(standard):
    ids = [c.id for c in load_catalog(standard)['controls']]
    assert len(ids) == len(set(ids)), f'{standard} 条款 ID 重复'


@pytest.mark.parametrize('standard', STANDARDS)
def test_every_check_is_registered(standard):
    """条款引用的评估器必须真实存在，否则运行期只会静默降级为『证据不足』"""
    for c in load_catalog(standard)['controls']:
        if c.check:
            assert c.check in CHECK_REGISTRY, f'{c.id} 引用了未注册的评估器 {c.check}'


@pytest.mark.parametrize('standard', STANDARDS)
def test_control_fields_are_sane(standard):
    for c in load_catalog(standard)['controls']:
        assert c.mode in (MODE_AUTO, MODE_QUESTIONNAIRE, MODE_HYBRID), c.id
        assert c.scope in ('org', 'system'), c.id
        assert c.weight > 0, c.id
        assert c.domain and c.title and c.requirement, c.id
        # auto/hybrid 必须给出评估器，否则模式声明与能力不符
        if c.mode in (MODE_AUTO, MODE_HYBRID):
            assert c.check, f'{c.id} 声明为 {c.mode} 却未指定 check'
        # questionnaire/hybrid 必须给出问题文本，否则问卷页是空白项
        if c.needs_questionnaire:
            assert c.question, f'{c.id} 需要问卷却未提供 question'


# ============================================================
# 路径穿越防护
# ============================================================
@pytest.mark.parametrize('evil', [
    '../../../../etc/passwd',
    '..\\..\\..\\Users\\someone\\.claude\\settings',   # Windows 上 \ 是路径分隔符
    'compliance_controls/../../secrets',
    'a/b',
    '..', '.', '',
    None,
])
def test_load_catalog_rejects_path_traversal(evil):
    """standard 来自 REST 路径参数与 JSON body，必须挡住目录外读取"""
    with pytest.raises(FileNotFoundError):
        load_catalog(evil)


def test_load_catalog_rejects_unknown_but_clean_name():
    with pytest.raises(FileNotFoundError):
        load_catalog('not_a_real_standard')


def test_load_catalog_accepts_known_standards():
    for std in STANDARDS:
        assert load_catalog(std)['standard'] == std


def test_engine_init_rejects_traversal():
    """经引擎构造函数进入的同一路径也必须被拦下"""
    with pytest.raises(FileNotFoundError):
        ComplianceEngine('..\\..\\config')


def test_dengbao_levels_cover_l2_and_l3():
    controls = load_catalog('dengbao')['controls']
    l2 = [c for c in controls if c.applies_to_level('L2')]
    l3 = [c for c in controls if c.applies_to_level('L3')]
    assert len(l2) >= 40
    # 三级要求严于二级
    assert len(l3) > len(l2)


# ============================================================
# AI 降级表 —— 逐行锁定（改动 score_factor 必须同步改这里）
# ============================================================
@pytest.mark.parametrize('ai', [AI_NOT_RUN, AI_ENDORSED, AI_INCOMPLETE])
def test_score_pass_full_credit(ai):
    """符合 + 认可/未运行/未完成 → 1.0"""
    assert score_factor(STATUS_PASS, ai) == 1.0


def test_score_pass_doubted_halved():
    """符合 + 存疑 → 0.5"""
    assert score_factor(STATUS_PASS, AI_DOUBTED) == 0.5


def test_score_pass_conflict_zero():
    """符合 + 矛盾 → 0.0"""
    assert score_factor(STATUS_PASS, AI_CONFLICT) == 0.0


@pytest.mark.parametrize('ai', AI_STATUSES)
def test_score_partial_always_half(ai):
    """部分符合 + 任意 AI 状态 → 0.5"""
    assert score_factor(STATUS_PARTIAL, ai) == 0.5


@pytest.mark.parametrize('ai', AI_STATUSES)
def test_score_fail_always_zero(ai):
    """不符合 + 任意 AI 状态 → 0.0"""
    assert score_factor(STATUS_FAIL, ai) == 0.0


@pytest.mark.parametrize('status', [STATUS_NA, STATUS_UNFILLED, STATUS_INSUFFICIENT])
@pytest.mark.parametrize('ai', AI_STATUSES)
def test_score_excluded_from_denominator(status, ai):
    """不适用/未填报/证据不足 一律不计入分母"""
    assert score_factor(status, ai) is None


def test_score_factor_default_ai_is_not_run():
    assert score_factor(STATUS_PASS) == score_factor(STATUS_PASS, AI_NOT_RUN)


# ============================================================
# 严重程度映射
# ============================================================
def test_severity_high_weight_fail_is_critical():
    assert severity_for(STATUS_FAIL, 2.0) == 'CRITICAL'
    assert severity_for(STATUS_FAIL, 1.0) == 'HIGH'


def test_severity_non_scored_is_info():
    for st in (STATUS_NA, STATUS_UNFILLED, STATUS_INSUFFICIENT):
        assert severity_for(st) == 'INFO'


# ============================================================
# 证据判定：没有证据 ≠ 合规
# ============================================================
def test_evidence_missing_reports_insufficient_not_pass():
    ev = EvidenceBundle(target='10.0.0.1')          # 空证据
    ctl = ComplianceControl(
        id='T-01', standard='t', domain='D', category='C',
        title='端口检查', requirement='R',
        mode=MODE_AUTO, check='check_db_exposure', evidence_type='port_scan',
    )
    eng = _engine_with([ctl])
    r = eng.evaluate(ev)['results'][0]
    assert r['status'] == STATUS_INSUFFICIENT
    assert r['status'] != STATUS_PASS


def test_unknown_checker_reports_insufficient():
    ctl = ComplianceControl(
        id='T-02', standard='t', domain='D', category='C',
        title='不存在的评估器', requirement='R',
        mode=MODE_AUTO, check='check_does_not_exist',
    )
    r = _engine_with([ctl]).evaluate(EvidenceBundle())['results'][0]
    assert r['status'] == STATUS_INSUFFICIENT
    assert '未实现的评估器' in r['detail']


def test_checker_exception_does_not_become_pass(monkeypatch):
    """评估器崩溃时必须报『证据不足』，绝不能静默判为符合"""
    def boom(evidence, control):
        raise RuntimeError('评估器炸了')

    monkeypatch.setitem(compliance_checks.CHECK_REGISTRY, 'check_boom', boom)
    ctl = ComplianceControl(
        id='T-03', standard='t', domain='D', category='C',
        title='崩溃', requirement='R', mode=MODE_AUTO, check='check_boom',
    )
    r = _engine_with([ctl]).evaluate(EvidenceBundle())['results'][0]
    assert r['status'] == STATUS_INSUFFICIENT
    assert '自动评估异常' in r['detail']


# ============================================================
# hybrid 合并：取较差者
# ============================================================
@pytest.mark.parametrize('auto,manual,expected', [
    (STATUS_PASS,    STATUS_FAIL,       STATUS_FAIL),
    (STATUS_FAIL,    STATUS_PASS,       STATUS_FAIL),
    (STATUS_PASS,    STATUS_PARTIAL,    STATUS_PARTIAL),
    (STATUS_PARTIAL, STATUS_PASS,       STATUS_PARTIAL),
    (STATUS_PASS,    STATUS_PASS,       STATUS_PASS),
    # 一侧无结论时取有结论的一侧
    (STATUS_INSUFFICIENT, STATUS_PASS,  STATUS_PASS),
    (STATUS_PASS, STATUS_UNFILLED,      STATUS_PASS),
    # 两侧都无结论：优先暴露可操作的『未填报』
    (STATUS_INSUFFICIENT, STATUS_UNFILLED, STATUS_UNFILLED),
    # 人工明确填的『不适用』是对适用性的定论，不得被技术侧的『证据不足』改写
    (STATUS_INSUFFICIENT, STATUS_NA, STATUS_NA),
])
def test_merge_hybrid_takes_worse(auto, manual, expected):
    assert ComplianceEngine._merge_hybrid(auto, manual) == expected


def test_explicit_na_survives_end_to_end():
    """人工填『不适用』的 hybrid 条款，在无技术证据时应保持不适用并排除出分母"""
    eng = ComplianceEngine('dengbao')
    agg = eng.evaluate(EvidenceBundle(target='10.0.0.1'),
                       answers={'DB-CN-02': {'status': STATUS_NA, 'note': '该系统不涉及'}},
                       level='L3')
    row = next(r for r in agg['results'] if r['control_id'] == 'DB-CN-02')
    assert row['status'] == STATUS_NA
    assert score_factor(row['status']) is None


def test_auto_verdict_still_outranks_na():
    """技术侧有实质结论时仍压过人工的『不适用』——扫到问题就说明条款适用"""
    assert ComplianceEngine._merge_hybrid(STATUS_FAIL, STATUS_NA) == STATUS_FAIL


def test_hybrid_manual_fail_overrides_auto_pass(monkeypatch):
    monkeypatch.setitem(compliance_checks.CHECK_REGISTRY, 'check_always_pass',
                        lambda e, c: {'status': STATUS_PASS, 'detail': '技术侧通过'})
    ctl = ComplianceControl(
        id='T-04', standard='t', domain='D', category='C',
        title='混合', requirement='R', mode=MODE_HYBRID,
        check='check_always_pass', question='填报？',
    )
    eng = _engine_with([ctl])
    r = eng.evaluate(EvidenceBundle(),
                     answers={'T-04': {'status': STATUS_FAIL, 'note': '制度缺失'}})['results'][0]
    assert r['status'] == STATUS_FAIL
    assert '技术侧通过' in r['detail'] and '制度缺失' in r['detail']


# ============================================================
# 问卷条款
# ============================================================
def test_questionnaire_unanswered_is_unfilled():
    ctl = _q_control('T-05')
    r = _engine_with([ctl]).evaluate(EvidenceBundle())['results'][0]
    assert r['status'] == STATUS_UNFILLED
    assert r['verdict_source'] == SOURCE_QUESTIONNAIRE


def test_questionnaire_answer_applied():
    ctl = _q_control('T-06')
    r = _engine_with([ctl]).evaluate(
        EvidenceBundle(),
        answers={'T-06': {'status': STATUS_PARTIAL, 'note': '部分落实'}})['results'][0]
    assert r['status'] == STATUS_PARTIAL
    assert r['detail'] == '部分落实'


def test_invalid_answer_status_ignored():
    """填报状态非法时不得被采信，退回未填报"""
    ctl = _q_control('T-07')
    r = _engine_with([ctl]).evaluate(
        EvidenceBundle(), answers={'T-07': {'status': '随便写的'}})['results'][0]
    assert r['status'] == STATUS_UNFILLED


def test_completion_counts_only_real_human_answers():
    """问卷完成度必须反映『人填了多少』，不能把 hybrid 的自动判定算进去。

    这是强制披露里的数字，虚报等于谎报人工投入。
    """
    eng = ComplianceEngine('dengbao')
    # 明文 Telnet 会让一批 hybrid 条款被自动判为不符合（状态不再是『未填报』）
    ev = build_evidence([{'host': '10.0.0.1', 'port': 23, 'protocol': 'tcp',
                          'state': 'open', 'service': 'telnet',
                          'severity': 'HIGH', 'description': 'Telnet 明文'}],
                        target='10.0.0.1')
    agg = eng.evaluate(ev, answers={}, level='L3')
    assert agg['counts'][STATUS_FAIL] > 0, '前提不成立：应有条款被自动判为不符合'
    assert agg['questionnaire_completion'] == 0.0, '人一条都没填，完成度必须是 0'

    agg2 = eng.evaluate(ev, answers={'DB-PE-01': {'status': STATUS_PASS}}, level='L3')
    expected = round(1 / agg2['questionnaire_total'], 4)
    assert agg2['questionnaire_completion'] == expected


def test_completion_falls_back_to_answer_dict():
    """手工拼装的结果字典没有 _answered 标记时，回退看 answer 子字典"""
    results = [
        {'control_id': 'A', '_mode': MODE_QUESTIONNAIRE, 'status': STATUS_PASS,
         'domain': 'D', '_weight': 1.0, 'answer': {'status': STATUS_PASS}},
        {'control_id': 'B', '_mode': MODE_HYBRID, 'status': STATUS_FAIL,
         'domain': 'D', '_weight': 1.0, 'answer': {}},          # 自动判出来的，人没填
    ]
    agg = ComplianceEngine.summarize(results)
    assert agg['questionnaire_total'] == 2
    assert agg['questionnaire_completion'] == 0.5


def test_questionnaire_completion_rate():
    ctls = [_q_control('T-08'), _q_control('T-09'), _q_control('T-10')]
    agg = _engine_with(ctls).evaluate(
        EvidenceBundle(), answers={'T-08': {'status': STATUS_PASS}})
    assert agg['questionnaire_total'] == 3
    # 引擎统一 round(...,4)，因此按四位小数比对
    assert agg['questionnaire_completion'] == round(1 / 3, 4)


# ============================================================
# AI 研判合入
# ============================================================
def test_ai_conflict_forces_fail():
    """AI 判定填报与技术事实矛盾 → 强制改判不符合，自评不得凌驾于硬事实"""
    results = [{'control_id': 'X', 'status': STATUS_PASS, 'severity': 'LOW',
                'detail': '自评符合', '_weight': 2.0}]
    out = ComplianceEngine.apply_ai_verdicts(
        results, {'X': {'ai_status': AI_CONFLICT, 'reasoning': '扫到明文端口'}})
    assert out[0]['status'] == STATUS_FAIL
    assert out[0]['severity'] == 'CRITICAL'
    assert out[0]['verdict_source'] == SOURCE_AI_ASSISTED
    assert '强制改判' in out[0]['detail']


def test_ai_doubted_keeps_status_but_halves_score():
    results = [{'control_id': 'X', 'status': STATUS_PASS, 'severity': 'LOW', '_weight': 1.0}]
    out = ComplianceEngine.apply_ai_verdicts(results, {'X': {'ai_status': AI_DOUBTED}})
    assert out[0]['status'] == STATUS_PASS
    agg = ComplianceEngine.summarize(out)
    assert agg['compliance_rate'] == 0.5


def test_ai_endorsed_keeps_full_score():
    results = [{'control_id': 'X', 'status': STATUS_PASS, 'severity': 'LOW', '_weight': 1.0}]
    out = ComplianceEngine.apply_ai_verdicts(results, {'X': {'ai_status': AI_ENDORSED}})
    assert ComplianceEngine.summarize(out)['compliance_rate'] == 1.0


def test_ai_verdict_for_unknown_control_ignored():
    results = [{'control_id': 'X', 'status': STATUS_PASS, '_weight': 1.0}]
    out = ComplianceEngine.apply_ai_verdicts(results, {'NOT-THERE': {'ai_status': AI_CONFLICT}})
    assert out[0]['status'] == STATUS_PASS
    assert out[0].get('ai_status', AI_NOT_RUN) == AI_NOT_RUN


def test_ai_conflict_does_not_upgrade_fail():
    """已经是不符合的条款不会因 AI 矛盾而被改成别的状态"""
    results = [{'control_id': 'X', 'status': STATUS_FAIL, 'severity': 'HIGH', '_weight': 1.0}]
    out = ComplianceEngine.apply_ai_verdicts(results, {'X': {'ai_status': AI_CONFLICT}})
    assert out[0]['status'] == STATUS_FAIL


# ============================================================
# 汇总计分
# ============================================================
def test_summarize_excludes_na_and_unfilled_from_denominator():
    results = [
        {'control_id': 'A', 'status': STATUS_PASS, 'domain': 'D', '_weight': 1.0},
        {'control_id': 'B', 'status': STATUS_FAIL, 'domain': 'D', '_weight': 1.0},
        {'control_id': 'C', 'status': STATUS_NA, 'domain': 'D', '_weight': 1.0},
        {'control_id': 'D', 'status': STATUS_UNFILLED, 'domain': 'D', '_weight': 1.0},
        {'control_id': 'E', 'status': STATUS_INSUFFICIENT, 'domain': 'D', '_weight': 1.0},
    ]
    agg = ComplianceEngine.summarize(results)
    assert agg['counts']['total'] == 5
    assert agg['scored_total'] == 2
    assert agg['compliance_rate'] == 0.5      # 1 符合 / 2 计分
    assert agg['score'] == 50


def test_summarize_weighted():
    """权重影响合规率：一条 weight=3 的不符合比 weight=1 的更拉低分数"""
    results = [
        {'control_id': 'A', 'status': STATUS_PASS, 'domain': 'D', '_weight': 1.0},
        {'control_id': 'B', 'status': STATUS_FAIL, 'domain': 'D', '_weight': 3.0},
    ]
    assert ComplianceEngine.summarize(results)['compliance_rate'] == 0.25


def test_summarize_by_domain():
    results = [
        {'control_id': 'A', 'status': STATUS_PASS, 'domain': '安全通信网络', '_weight': 1.0},
        {'control_id': 'B', 'status': STATUS_FAIL, 'domain': '安全通信网络', '_weight': 1.0},
        {'control_id': 'C', 'status': STATUS_PASS, 'domain': '安全管理制度', '_weight': 1.0},
    ]
    by = ComplianceEngine.summarize(results)['by_domain']
    assert by['安全通信网络']['compliance_rate'] == 0.5
    assert by['安全通信网络']['scored'] == 2
    assert by['安全管理制度']['compliance_rate'] == 1.0


def test_summarize_all_excluded_yields_none_rate():
    """全部条款都不计分时合规率为 None，而不是 0 或 100"""
    results = [{'control_id': 'A', 'status': STATUS_UNFILLED, 'domain': 'D', '_weight': 1.0}]
    agg = ComplianceEngine.summarize(results)
    assert agg['compliance_rate'] is None
    assert agg['score'] is None


def test_summarize_counts_all_statuses():
    results = [{'control_id': str(i), 'status': s, 'domain': 'D', '_weight': 1.0}
               for i, s in enumerate(ALL_STATUSES)]
    counts = ComplianceEngine.summarize(results)['counts']
    for s in ALL_STATUSES:
        assert counts[s] == 1


# ============================================================
# 端到端
# ============================================================
def test_evaluate_returns_metadata():
    agg = _engine_with([_q_control('T-11')]).evaluate(
        EvidenceBundle(target='192.168.1.10', scope_key='OA系统'), level='L3')
    assert agg['level'] == 'L3'
    assert agg['target'] == '192.168.1.10'
    assert agg['scope_key'] == 'OA系统'
    assert agg['timestamp'] and agg['duration'] >= 0


def test_level_filter_excludes_l3_only_controls():
    l3_only = _q_control('T-12', levels={'L3'})
    both = _q_control('T-13', levels={'L2', 'L3'})
    eng = _engine_with([l3_only, both])
    assert len(eng.evaluate(EvidenceBundle(), level='L2')['results']) == 1
    assert len(eng.evaluate(EvidenceBundle(), level='L3')['results']) == 2
    assert len(eng.evaluate(EvidenceBundle(), level='ALL')['results']) == 2


def test_real_catalog_evaluates_without_crash():
    """用真实等保目录跑一遍空证据评估，确保全部条款可判定且不抛异常"""
    eng = ComplianceEngine('dengbao')
    agg = eng.evaluate(EvidenceBundle(target='10.0.0.1'), level='L3')
    assert agg['counts']['total'] == len(eng.controls_for_level('L3'))
    for r in agg['results']:
        assert r['status'] in ALL_STATUSES
    # 空证据下不应凭空出现「符合」
    assert agg['counts'][STATUS_PASS] == 0


# ============================================================
# 辅助
# ============================================================
def _engine_with(controls):
    """构造引擎并替换为测试用条款集（避免依赖真实目录内容）"""
    eng = ComplianceEngine('dengbao')
    eng.controls = list(controls)
    return eng


def _q_control(cid, levels=None):
    return ComplianceControl(
        id=cid, standard='t', domain='D', category='C',
        title='问卷条款', requirement='R', mode=MODE_QUESTIONNAIRE,
        question='是否落实？', levels=levels or {'ALL'},
    )
