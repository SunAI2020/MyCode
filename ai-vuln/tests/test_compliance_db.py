# -*- coding: utf-8 -*-
"""合规结果数据库测试 — 历史保存、问卷 UPSERT、作用域复用"""
import pytest

from compliance_engine import (
    ComplianceEngine, EvidenceBundle,
    STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL,
)


def _agg(standard='dengbao', scope_key='ORG', answers=None, level='L3'):
    eng = ComplianceEngine(standard)
    return eng.evaluate(EvidenceBundle(target='10.0.0.1', scope_key=scope_key),
                        answers=answers or {}, level=level)


# ============================================================
# 检查结果
# ============================================================
class TestComplianceResults:
    def test_save_and_get_detail(self, compliance_db):
        agg = _agg()
        hid = compliance_db.save_result(agg)
        assert hid > 0

        detail = compliance_db.get_detail(hid)
        assert detail is not None
        assert detail['history']['standard'] == 'dengbao'
        assert detail['history']['level'] == 'L3'
        assert detail['history']['total'] == agg['counts']['total']
        assert len(detail['results']) == agg['counts']['total']

    def test_get_detail_missing_returns_none(self, compliance_db):
        """查不到就返回 None，不返回空壳结构骗调用方"""
        assert compliance_db.get_detail(999999) is None

    def test_json_columns_round_trip(self, compliance_db):
        hid = compliance_db.save_result(_agg())
        detail = compliance_db.get_detail(hid)
        assert isinstance(detail['history']['by_domain'], dict)
        assert detail['history']['by_domain']          # 等保目录有多个域
        assert isinstance(detail['history']['summary'], dict)
        assert 'counts' in detail['history']['summary']

    def test_control_rows_carry_weight_and_mode(self, compliance_db):
        hid = compliance_db.save_result(_agg())
        rows = compliance_db.get_detail(hid)['results']
        assert all(r['control_id'] for r in rows)
        assert all(r['weight'] > 0 for r in rows)
        assert any(r['mode'] == 'hybrid' for r in rows)

    def test_ai_enabled_flag_persisted(self, compliance_db):
        hid = compliance_db.save_result(_agg(), ai_enabled=True)
        assert compliance_db.get_detail(hid)['history']['ai_enabled'] == 1

    def test_history_ordered_desc_and_filtered(self, compliance_db):
        compliance_db.save_result(_agg('dengbao'))
        compliance_db.save_result(_agg('cii', level='ALL'))
        compliance_db.save_result(_agg('dengbao'))

        assert len(compliance_db.get_history()) == 3
        db_only = compliance_db.get_history('dengbao')
        assert len(db_only) == 2
        assert db_only[0]['id'] > db_only[1]['id']       # 最新在前

    def test_get_latest_by_scope(self, compliance_db):
        compliance_db.save_result(_agg(scope_key='ORG'))
        hid = compliance_db.save_result(_agg(scope_key='OA系统'))
        latest = compliance_db.get_latest('dengbao', 'OA系统')
        assert latest['id'] == hid
        assert compliance_db.get_latest('dengbao', '不存在的系统') is None

    def test_delete_result_removes_children(self, compliance_db):
        hid = compliance_db.save_result(_agg())
        compliance_db.delete_result(hid)
        assert compliance_db.get_detail(hid) is None
        assert compliance_db.get_history() == []

    def test_statistics(self, compliance_db):
        compliance_db.save_result(_agg('dengbao'))
        compliance_db.save_result(_agg('cii', level='ALL'))
        stats = compliance_db.get_statistics()
        assert stats['total_checks'] == 2
        assert set(stats['by_standard']) == {'dengbao', 'cii'}
        assert stats['by_standard']['dengbao']['checks'] == 1


# ============================================================
# 问卷答案
# ============================================================
class TestQuestionnaireAnswers:
    def test_upsert_inserts_then_updates(self, compliance_db):
        compliance_db.upsert_answer('dengbao', 'DB-PE-02', STATUS_PASS, note='已装门禁')
        compliance_db.upsert_answer('dengbao', 'DB-PE-02', STATUS_PARTIAL, note='复核后改判')

        answers = compliance_db.get_answers('dengbao')
        assert len(answers) == 1                      # UNIQUE 约束下不产生第二行
        assert answers['DB-PE-02']['status'] == STATUS_PARTIAL
        assert answers['DB-PE-02']['note'] == '复核后改判'

    def test_answers_isolated_by_standard(self, compliance_db):
        compliance_db.upsert_answer('dengbao', 'X-01', STATUS_PASS)
        compliance_db.upsert_answer('cii', 'X-01', STATUS_FAIL)
        assert compliance_db.get_answers('dengbao')['X-01']['status'] == STATUS_PASS
        assert compliance_db.get_answers('cii')['X-01']['status'] == STATUS_FAIL

    def test_org_answers_reused_by_business_system(self, compliance_db):
        """组织级条款填一次，所有业务系统复用，不必逐系统重复填报"""
        compliance_db.upsert_answer('dengbao', 'DB-MS-01', STATUS_PASS)          # ORG
        compliance_db.upsert_answer('dengbao', 'DB-CM-01', STATUS_PASS, scope_key='OA系统')

        oa = compliance_db.get_answers('dengbao', 'OA系统')
        assert set(oa) == {'DB-MS-01', 'DB-CM-01'}
        # 反向不成立：ORG 视角看不到业务系统的答案
        assert set(compliance_db.get_answers('dengbao')) == {'DB-MS-01'}

    def test_system_answer_overrides_org(self, compliance_db):
        compliance_db.upsert_answer('dengbao', 'DB-MS-01', STATUS_PASS)
        compliance_db.upsert_answer('dengbao', 'DB-MS-01', STATUS_FAIL, scope_key='OA系统')
        assert compliance_db.get_answers('dengbao', 'OA系统')['DB-MS-01']['status'] == STATUS_FAIL
        assert compliance_db.get_answers('dengbao')['DB-MS-01']['status'] == STATUS_PASS

    def test_include_org_can_be_disabled(self, compliance_db):
        compliance_db.upsert_answer('dengbao', 'DB-MS-01', STATUS_PASS)
        assert compliance_db.get_answers('dengbao', 'OA系统', include_org=False) == {}

    def test_delete_answer(self, compliance_db):
        compliance_db.upsert_answer('dengbao', 'DB-PE-02', STATUS_PASS)
        compliance_db.delete_answer('dengbao', 'DB-PE-02')
        assert compliance_db.get_answers('dengbao') == {}

    def test_get_scope_keys(self, compliance_db):
        compliance_db.upsert_answer('dengbao', 'A', STATUS_PASS)
        compliance_db.upsert_answer('dengbao', 'B', STATUS_PASS, scope_key='OA系统')
        assert compliance_db.get_scope_keys('dengbao') == ['OA系统', 'ORG']

    def test_answers_feed_engine_and_raise_score(self, compliance_db):
        """填报答案后合规率应上升 —— 打通『问卷 → 引擎 → 落库』闭环"""
        before = compliance_db.save_result(_agg())
        rate_before = compliance_db.get_detail(before)['history']['compliance_rate']

        for cid in ('DB-PE-01', 'DB-PE-02', 'DB-PE-03', 'DB-MS-01', 'DB-MS-02'):
            compliance_db.upsert_answer('dengbao', cid, STATUS_PASS, note='已落实')
        answers = compliance_db.get_answers('dengbao')
        after = compliance_db.save_result(_agg(answers=answers))
        detail = compliance_db.get_detail(after)

        assert detail['history']['pass_count'] == 5
        assert detail['history']['compliance_rate'] > (rate_before or 0)


# ============================================================
# 清库与门面
# ============================================================
def test_clear_all_wipes_three_tables(compliance_db):
    compliance_db.save_result(_agg())
    compliance_db.upsert_answer('dengbao', 'DB-PE-02', STATUS_PASS)
    compliance_db.clear_all()
    assert compliance_db.get_history() == []
    assert compliance_db.get_answers('dengbao') == {}
    assert compliance_db.get_statistics()['total_checks'] == 0


def test_facade_registers_compliance(patch_db_connect):
    """Database 门面必须挂上第六个库并转发合规方法"""
    from database import Database
    db = Database()
    try:
        assert db.compliance is not None
        hid = db.save_compliance_result(_agg())
        assert db.get_compliance_detail(hid) is not None
        db.upsert_questionnaire_answer('dengbao', 'DB-PE-02', STATUS_PASS)
        assert 'DB-PE-02' in db.get_questionnaire_answers('dengbao')
        assert db.get_latest_compliance('dengbao', 'ORG')['id'] == hid
        assert len(db.get_compliance_history('dengbao')) == 1
    finally:
        db.close()


def test_work_types_include_three_compliance_entries(patch_db_connect):
    """今日工作矩阵须新增三类合规工作，否则合规操作在仪表盘不可见"""
    from database import Database
    db = Database()
    try:
        matrix = db.get_today_work_status_matrix()
        for wt in ('等保合规', '关基合规', '数据安全合规'):
            assert wt in matrix
            assert set(matrix[wt]) == {'已完成', '进行中', '计划中', '被终止'}
    finally:
        db.close()
