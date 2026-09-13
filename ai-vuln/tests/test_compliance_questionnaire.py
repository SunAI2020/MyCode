# -*- coding: utf-8 -*-
"""合规问卷引擎与 AI 研判层测试

重点锁定：AI 调用失败必须判『未完成』而非『认可』（方向与 ai_scan_enhancer 相反）。
"""
import pytest

import compliance_ai
from compliance_ai import (
    ComplianceAI, evidence_digest, merge_verdicts, _parse_json, _as_items,
)
from compliance_engine import (
    EvidenceBundle, ComplianceControl,
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL, STATUS_NA, STATUS_UNFILLED, STATUS_INSUFFICIENT,
    AI_ENDORSED, AI_DOUBTED, AI_CONFLICT, AI_INCOMPLETE, MODE_QUESTIONNAIRE,
)
from compliance_questionnaire import (
    QuestionnaireEngine, resolve_scope_key, system_scope_key, normalize_status,
    ORG_SCOPE, DEFAULT_SYSTEM_SCOPE,
)


# ============================================================
# scope_key 解析
# ============================================================
def _ctl(cid='T-01', scope='system'):
    return ComplianceControl(id=cid, standard='t', domain='D', category='C',
                             title='T', requirement='R', mode=MODE_QUESTIONNAIRE,
                             question='Q', scope=scope)


def test_org_control_always_maps_to_org_scope():
    assert resolve_scope_key(_ctl(scope='org'), 'OA系统') == ORG_SCOPE
    assert resolve_scope_key(_ctl(scope='org'), '') == ORG_SCOPE


def test_system_control_uses_business_system():
    assert resolve_scope_key(_ctl(scope='system'), 'OA系统') == 'OA系统'


def test_system_control_falls_back_to_default():
    assert resolve_scope_key(_ctl(scope='system'), '') == DEFAULT_SYSTEM_SCOPE
    assert resolve_scope_key(_ctl(scope='system'), '   ') == DEFAULT_SYSTEM_SCOPE
    assert system_scope_key(None) == DEFAULT_SYSTEM_SCOPE


# ============================================================
# 状态归一化
# ============================================================
@pytest.mark.parametrize('raw,expected', [
    ('符合', STATUS_PASS), ('部分符合', STATUS_PARTIAL),
    ('不符合', STATUS_FAIL), ('不适用', STATUS_NA),
    ('合规', STATUS_PASS), ('PASS', STATUS_PASS), ('yes', STATUS_PASS),
    ('不合规', STATUS_FAIL), ('N/A', STATUS_NA),
])
def test_normalize_known_statuses(raw, expected):
    assert normalize_status(raw) == expected


@pytest.mark.parametrize('raw', ['', None, '随便写的', STATUS_UNFILLED, STATUS_INSUFFICIENT])
def test_normalize_rejects_unknown(raw):
    """认不出来就返回 None，绝不猜成『符合』"""
    assert normalize_status(raw) is None


# ============================================================
# 问卷引擎
# ============================================================
class TestQuestionnaireEngine:
    def test_lists_only_questionnaire_and_hybrid(self):
        q = QuestionnaireEngine('dengbao', level='L3')
        controls = q.controls()
        assert controls
        assert all(c.needs_questionnaire for c in controls)

    def test_grouped_by_domain(self):
        q = QuestionnaireEngine('dengbao', level='L3')
        grouped = q.controls_by_domain()
        assert '安全物理环境' in grouped
        assert sum(len(v) for v in grouped.values()) == len(q.controls())

    def test_readonly_mode_refuses_save(self):
        q = QuestionnaireEngine('dengbao')
        assert q.save_answer('DB-PE-02', STATUS_PASS) is False

    def test_save_and_load(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db, level='L3')
        assert q.save_answer('DB-PE-02', STATUS_PASS, note='已装门禁') is True
        assert q.load_answers()['DB-PE-02']['status'] == STATUS_PASS

    def test_save_rejects_unknown_control(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db)
        assert q.save_answer('NOT-A-REAL-ID', STATUS_PASS) is False
        assert q.load_answers() == {}

    def test_save_rejects_invalid_status(self, compliance_db):
        """非法状态不得静默落库"""
        q = QuestionnaireEngine('dengbao', compliance_db)
        assert q.save_answer('DB-PE-02', '大概符合吧') is False
        assert q.load_answers() == {}

    def test_org_control_saved_under_org_even_with_business_system(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db)
        # DB-PE-02 是 org 级条款
        q.save_answer('DB-PE-02', STATUS_PASS, business_system='OA系统')
        assert compliance_db.get_answers('dengbao', ORG_SCOPE)['DB-PE-02']['status'] == STATUS_PASS
        # 另一个业务系统也能读到同一份答案
        assert 'DB-PE-02' in q.load_answers('财务系统')

    def test_system_control_isolated_per_business_system(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db)
        # DB-CM-01 是 system 级条款
        q.save_answer('DB-CM-01', STATUS_PASS, business_system='OA系统')
        assert 'DB-CM-01' in q.load_answers('OA系统')
        assert 'DB-CM-01' not in q.load_answers('财务系统')

    def test_batch_save_reports_rejections(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db)
        stats = q.save_answers({
            'DB-PE-01': {'status': STATUS_PASS},
            'DB-PE-02': {'status': '瞎写'},
            'NOPE-99': {'status': STATUS_PASS},
        })
        assert stats == {'saved': 1, 'rejected': 2}

    def test_progress_and_pending(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db, level='L3')
        total = len(q.controls())
        before = q.progress()
        assert before['total'] == total and before['filled'] == 0 and before['rate'] == 0.0

        q.save_answer('DB-PE-01', STATUS_PASS)
        q.save_answer('DB-PE-02', STATUS_PARTIAL)
        after = q.progress()
        assert after['filled'] == 2
        assert after['pending'] == total - 2
        assert len(q.pending_controls()) == total - 2
        assert after['by_domain']['安全物理环境']['filled'] == 2

    def test_clear_answer(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db)
        q.save_answer('DB-PE-02', STATUS_PASS)
        assert q.clear_answer('DB-PE-02') is True
        assert q.load_answers() == {}

    def test_to_rows_marks_unanswered(self, compliance_db):
        q = QuestionnaireEngine('dengbao', compliance_db, level='L3')
        q.save_answer('DB-PE-01', STATUS_PASS, note='已确认')
        rows = {r['control_id']: r for r in q.to_rows()}
        assert rows['DB-PE-01']['answered'] is True
        assert rows['DB-PE-01']['note'] == '已确认'
        assert rows['DB-PE-02']['answered'] is False
        assert rows['DB-PE-02']['status'] == STATUS_UNFILLED
        assert rows['DB-PE-02']['options']            # 问卷选项必须有值供界面渲染


# ============================================================
# AI 研判：失败方向
# ============================================================
class _FakeClient:
    """可控的 AIClient 替身，避免测试触发真实 CLI 调用"""

    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls = 0

    def query(self, user_message, system_prompt=None, max_turns=1, timeout=300):
        self.calls += 1
        if self.raise_exc:
            raise self.raise_exc
        return self.response


@pytest.fixture
def ai(monkeypatch):
    """构造 ComplianceAI 并强制 available=True，避免依赖真实 CLI"""
    monkeypatch.setattr(compliance_ai, 'is_ai_available', lambda: True)
    monkeypatch.setattr(compliance_ai, 'AIClient', lambda **kw: _FakeClient())
    return ComplianceAI()


def _results(*statuses):
    return [{'control_id': f'C-{i}', 'title': 'T', 'requirement': 'R',
             'status': s, 'detail': '自评说明', '_weight': 1.0}
            for i, s in enumerate(statuses)]


class TestAIFailureDirection:
    def test_exception_yields_incomplete_not_endorsed(self, ai):
        ai.client = _FakeClient(raise_exc=RuntimeError('CLI 挂了'))
        out = ai.review_answers(_results(STATUS_PASS, STATUS_PASS))
        assert set(out) == {'C-0', 'C-1'}
        for v in out.values():
            assert v['ai_status'] == AI_INCOMPLETE
            assert v['ai_status'] != AI_ENDORSED

    def test_unparseable_response_yields_incomplete(self, ai):
        ai.client = _FakeClient(response='对不起我无法回答这个问题')
        out = ai.review_answers(_results(STATUS_PASS))
        assert out['C-0']['ai_status'] == AI_INCOMPLETE

    def test_empty_response_yields_incomplete(self, ai):
        ai.client = _FakeClient(response='')
        out = ai.cross_check(_results(STATUS_PASS), EvidenceBundle())
        assert out['C-0']['ai_status'] == AI_INCOMPLETE

    def test_missing_control_in_response_yields_incomplete(self, ai):
        ai.client = _FakeClient(response='[{"control_id":"C-0","ai_status":"认可"}]')
        out = ai.review_answers(_results(STATUS_PASS, STATUS_PASS))
        assert out['C-0']['ai_status'] == AI_ENDORSED
        assert out['C-1']['ai_status'] == AI_INCOMPLETE      # 模型漏答的那条

    def test_unrecognized_verdict_yields_incomplete(self, ai):
        """模型胡诌一个状态时不得被归入『认可』"""
        ai.client = _FakeClient(response='[{"control_id":"C-0","ai_status":"基本没问题"}]')
        out = ai.review_answers(_results(STATUS_PASS))
        assert out['C-0']['ai_status'] == AI_INCOMPLETE

    def test_ai_unavailable_yields_incomplete(self, monkeypatch):
        monkeypatch.setattr(compliance_ai, 'is_ai_available', lambda: False)
        monkeypatch.setattr(compliance_ai, 'AIClient', lambda **kw: _FakeClient())
        out = ComplianceAI().review_answers(_results(STATUS_PASS))
        assert out['C-0']['ai_status'] == AI_INCOMPLETE

    def test_incomplete_keeps_full_score_but_flags_not_verified(self):
        """未完成不惩罚分数（符合+未完成=1.0），但必须能被看出没核验过"""
        from compliance_engine import score_factor
        assert score_factor(STATUS_PASS, AI_INCOMPLETE) == 1.0
        assert AI_INCOMPLETE != AI_ENDORSED


class TestAIVerdicts:
    def test_endorsed_and_doubted_parsed(self, ai):
        ai.client = _FakeClient(response=(
            '```json\n[{"control_id":"C-0","ai_status":"认可","reasoning":"有据"},'
            '{"control_id":"C-1","ai_status":"存疑","reasoning":"缺证据",'
            '"recommendation":"补台账"}]\n```'))
        out = ai.review_answers(_results(STATUS_PASS, STATUS_PASS))
        assert out['C-0']['ai_status'] == AI_ENDORSED
        assert out['C-1']['ai_status'] == AI_DOUBTED
        assert out['C-1']['recommendation'] == '补台账'

    def test_cross_check_only_targets_pass_and_partial(self, ai):
        ai.client = _FakeClient(response='[]')
        out = ai.cross_check(_results(STATUS_PASS, STATUS_FAIL, STATUS_PARTIAL),
                             EvidenceBundle())
        assert set(out) == {'C-0', 'C-2'}       # 不符合项不参与比对

    def test_review_skips_unfilled_and_na(self, ai):
        ai.client = _FakeClient(response='[]')
        assert ai.review_answers(_results(STATUS_UNFILLED, STATUS_NA, STATUS_INSUFFICIENT)) == {}

    def test_conflict_flows_into_engine_and_forces_fail(self, ai):
        from compliance_engine import ComplianceEngine
        ai.client = _FakeClient(response=(
            '[{"control_id":"C-0","ai_status":"矛盾","reasoning":"扫到 Telnet 明文端口"}]'))
        results = _results(STATUS_PASS)
        verdicts = ai.cross_check(results, EvidenceBundle(
            open_ports=[{'port': 23, 'service': 'telnet'}]))
        merged = ComplianceEngine.apply_ai_verdicts(results, verdicts)
        assert merged[0]['status'] == STATUS_FAIL
        assert ComplianceEngine.summarize(merged)['compliance_rate'] == 0.0

    def test_suggest_answers_drops_invalid_status(self, ai):
        ai.client = _FakeClient(response=(
            '[{"control_id":"DB-PE-01","status":"大概符合","confidence":0.9},'
            '{"control_id":"DB-PE-02","status":"符合","confidence":"高"}]'))
        controls = [c for c in QuestionnaireEngine('dengbao').controls()
                    if c.id in ('DB-PE-01', 'DB-PE-02')]
        out = ai.suggest_answers(controls)
        assert out['DB-PE-01']['status'] is None            # 非法状态被丢弃
        assert out['DB-PE-02']['status'] == STATUS_PASS
        assert out['DB-PE-02']['confidence'] == 0.0         # 非法置信度归零

    def test_remediation_only_for_failing_controls(self, ai):
        ai.client = _FakeClient(response=(
            '[{"control_id":"C-0","remediation":"改这个"},'
            '{"control_id":"C-1","remediation":"改那个"}]'))
        out = ai.generate_remediation(_results(STATUS_FAIL, STATUS_PARTIAL, STATUS_PASS))
        assert set(out) <= {'C-0', 'C-1'}
        assert 'C-2' not in out

    def test_remediation_reports_truncation(self, ai):
        """截断必须显式告知，不能让调用方以为全都生成了"""
        ai.client = _FakeClient(response='[]')
        msgs = []
        ai.generate_remediation(_results(*([STATUS_FAIL] * 30)), top_n=5,
                                progress_callback=msgs.append)
        assert any('剩余 25 条未生成' in m for m in msgs)


# ============================================================
# 多轮结论合并
# ============================================================
class TestMergeVerdicts:
    """复核与交叉比对是两轮独立研判，合并必须取较严重者。

    早期用 dict.update() 后写覆盖前写，复核的『存疑』会被交叉比对的
    『认可』抹掉——把拿不准悄悄升级成没问题。
    """

    def test_doubt_survives_endorsement(self):
        review = {'C-0': {'ai_status': AI_DOUBTED, 'reasoning': '依据空泛'}}
        cross = {'C-0': {'ai_status': AI_ENDORSED, 'reasoning': '与事实不冲突'}}
        assert merge_verdicts(review, cross)['C-0']['ai_status'] == AI_DOUBTED
        # 顺序无关
        assert merge_verdicts(cross, review)['C-0']['ai_status'] == AI_DOUBTED

    def test_conflict_beats_everything(self):
        for other in (AI_ENDORSED, AI_DOUBTED, AI_INCOMPLETE):
            merged = merge_verdicts({'C-0': {'ai_status': other}},
                                    {'C-0': {'ai_status': AI_CONFLICT}})
            assert merged['C-0']['ai_status'] == AI_CONFLICT

    def test_real_verdict_beats_incomplete(self):
        """『未完成』不是结论，任何实质结论都应压过它"""
        merged = merge_verdicts({'C-0': {'ai_status': AI_INCOMPLETE}},
                                {'C-0': {'ai_status': AI_ENDORSED}})
        assert merged['C-0']['ai_status'] == AI_ENDORSED

    def test_disjoint_controls_all_kept(self):
        merged = merge_verdicts({'C-0': {'ai_status': AI_ENDORSED}},
                                {'C-1': {'ai_status': AI_DOUBTED}})
        assert set(merged) == {'C-0', 'C-1'}

    def test_empty_and_none_maps_tolerated(self):
        assert merge_verdicts({}, None, {'C-0': {'ai_status': AI_ENDORSED}})['C-0']
        assert merge_verdicts() == {}

    def test_reasoning_travels_with_winning_verdict(self):
        merged = merge_verdicts({'C-0': {'ai_status': AI_ENDORSED, 'reasoning': '认可理由'}},
                                {'C-0': {'ai_status': AI_DOUBTED, 'reasoning': '存疑理由'}})
        assert merged['C-0']['reasoning'] == '存疑理由'


# ============================================================
# 工具函数
# ============================================================
def test_evidence_digest_states_absence_explicitly():
    assert '未提供技术证据' in evidence_digest(None)
    assert '未发现' in evidence_digest(EvidenceBundle())


def test_evidence_digest_summarizes():
    ev = EvidenceBundle(
        open_ports=[{'port': 23, 'service': 'telnet'}, {'port': 443, 'service': 'https'}],
        vulnerabilities=[{'severity': 'HIGH', 'cve_id': 'CVE-2024-1', 'kev': True}],
        weak_passwords=[{'host': '10.0.0.1'}])
    digest = evidence_digest(ev)
    assert '开放端口(2)' in digest and '23/telnet' in digest
    assert 'CVE-2024-1' in digest and '弱口令: 1 处' in digest


def test_parse_json_tolerates_prose_wrapping():
    assert _parse_json('好的，结果如下：[{"a":1}] 以上') == [{'a': 1}]
    assert _parse_json('```json\n{"a":1}\n```') == {'a': 1}
    assert _parse_json('完全不是 JSON') is None


def test_as_items_unwraps_common_shapes():
    assert _as_items({'results': [{'control_id': 'X'}]}) == [{'control_id': 'X'}]
    assert _as_items({'control_id': 'X'}) == [{'control_id': 'X'}]
    assert _as_items('nonsense') == []
