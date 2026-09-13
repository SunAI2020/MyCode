# -*- coding: utf-8 -*-
"""合规检查 REST API 测试（TestClient，不起真实服务器）"""
import pytest

pytest.importorskip('fastapi')

from fastapi import FastAPI
from fastapi.testclient import TestClient

from compliance_engine import STATUS_PASS, STATUS_FAIL


@pytest.fixture
def client(patch_db_connect):
    from database import Database
    from api.dependencies import get_db
    from api.auth import verify_api_key
    from api.routers import compliance

    db = Database()
    app = FastAPI()
    app.include_router(compliance.router, prefix='/api/v1')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[verify_api_key] = lambda: 'test-key'

    with TestClient(app) as c:
        c.db = db
        yield c
    db.close()


def _body(resp):
    assert resp.status_code == 200, resp.text
    return resp.json()


# ============================================================
# 标准与历史
# ============================================================
def test_standards_lists_three(client):
    data = _body(client.get('/api/v1/compliance/standards'))['data']
    names = {d['standard'] for d in data}
    assert {'dengbao', 'cii', 'data_security'} <= names
    dengbao = next(d for d in data if d['standard'] == 'dengbao')
    assert dengbao['total_controls'] >= 40
    assert 'GB/T 22239-2019' in dengbao['standard_name']


def test_history_empty_initially(client):
    assert _body(client.get('/api/v1/compliance/history'))['data'] == []


# ============================================================
# 问卷
# ============================================================
def test_questionnaire_returns_rows_and_progress(client):
    data = _body(client.get('/api/v1/compliance/questionnaire/dengbao?level=L3'))['data']
    assert data['progress']['filled'] == 0
    assert data['progress']['total'] > 0
    assert len(data['rows']) == data['progress']['total']
    assert all(r['question'] for r in data['rows'])


def test_questionnaire_unknown_standard(client):
    body = _body(client.get('/api/v1/compliance/questionnaire/not_a_standard'))
    assert body['success'] is False
    assert '未知的合规标准' in body['message']


def test_put_answers_then_read_back(client):
    resp = client.put('/api/v1/compliance/questionnaire/dengbao', json={
        'business_system': 'OA系统',
        'answered_by': '张三',
        'answers': [
            {'control_id': 'DB-PE-01', 'status': STATUS_PASS, 'note': '已确认'},
            {'control_id': 'DB-PE-02', 'status': STATUS_FAIL, 'note': '无门禁'},
        ],
    })
    body = _body(resp)
    assert body['success'] is True
    assert body['data']['saved'] == 2 and body['data']['rejected'] == 0

    rows = _body(client.get(
        '/api/v1/compliance/questionnaire/dengbao?level=L3&business_system=OA系统'))['data']['rows']
    by_id = {r['control_id']: r for r in rows}
    assert by_id['DB-PE-01']['status'] == STATUS_PASS
    assert by_id['DB-PE-01']['answered_by'] == '张三'
    assert by_id['DB-PE-02']['note'] == '无门禁'


def test_put_answers_rejects_bad_input(client):
    """非法条款/状态被明确拒绝并计数，不能假装成功"""
    body = _body(client.put('/api/v1/compliance/questionnaire/dengbao', json={
        'answers': [
            {'control_id': 'DB-PE-01', 'status': STATUS_PASS},
            {'control_id': 'NOT-REAL', 'status': STATUS_PASS},
            {'control_id': 'DB-PE-02', 'status': '大概符合'},
        ],
    }))
    assert body['success'] is False
    assert body['data']['saved'] == 1
    assert body['data']['rejected'] == 2
    assert '被拒绝' in body['message']


def test_put_validates_required_fields(client):
    """control_id 为空由 Pydantic 拦下，返回 422"""
    resp = client.put('/api/v1/compliance/questionnaire/dengbao', json={
        'answers': [{'control_id': '', 'status': STATUS_PASS}]})
    assert resp.status_code == 422


# ============================================================
# 执行检查
# ============================================================
def test_check_without_scan_reports_no_evidence(client):
    body = _body(client.post('/api/v1/compliance/check',
                             json={'standard': 'dengbao', 'level': 'L3'}))
    data = body['data']
    assert data['evidence_used'] is False
    assert data['history_id'] > 0
    assert data['counts']['total'] > 0
    # 无证据无填报时不应凭空产生『符合』
    assert data['counts']['符合'] == 0


def test_check_unknown_standard(client):
    body = _body(client.post('/api/v1/compliance/check', json={'standard': 'nope'}))
    assert body['success'] is False


def test_check_with_missing_scan_id(client):
    body = _body(client.post('/api/v1/compliance/check',
                             json={'standard': 'dengbao', 'scan_id': 999999}))
    assert body['success'] is False
    assert '扫描任务不存在' in body['message']


def test_check_uses_scan_evidence(client):
    """给了扫描证据后，技术类条款应能作出判定而不再是『证据不足』"""
    tid = client.db.scan.create_task('10.0.0.1', 'quick')
    for row in [
        {'host': '10.0.0.1', 'port': 23, 'protocol': 'tcp', 'state': 'open',
         'service': 'telnet', 'severity': 'HIGH',
         'description': 'Telnet 明文传输'},
        {'host': '10.0.0.1', 'port': 443, 'protocol': 'tcp', 'state': 'open',
         'service': 'https', 'severity': 'INFO', 'description': ''},
    ]:
        client.db.scan.add_scan_result(tid, row)

    body = _body(client.post('/api/v1/compliance/check',
                             json={'standard': 'dengbao', 'level': 'L3', 'scan_id': tid}))
    data = body['data']
    assert data['evidence_used'] is True
    # 明文 Telnet 必须被技术检查抓成不符合
    assert data['counts']['不符合'] > 0
    assert data['auto_ratio'] > 0


def test_check_consumes_saved_answers(client):
    client.put('/api/v1/compliance/questionnaire/dengbao', json={
        'answers': [{'control_id': 'DB-PE-01', 'status': STATUS_PASS},
                    {'control_id': 'DB-PE-02', 'status': STATUS_PASS}]})
    data = _body(client.post('/api/v1/compliance/check',
                             json={'standard': 'dengbao', 'level': 'L3'}))['data']
    assert data['counts']['符合'] == 2
    assert data['compliance_rate'] == 1.0


# ============================================================
# 详情
# ============================================================
def test_detail_round_trip(client):
    hid = _body(client.post('/api/v1/compliance/check',
                            json={'standard': 'cii'}))['data']['history_id']
    detail = _body(client.get(f'/api/v1/compliance/{hid}'))['data']
    assert detail['history']['standard'] == 'cii'
    assert len(detail['results']) == detail['history']['total']


def test_detail_missing_returns_not_found(client):
    body = _body(client.get('/api/v1/compliance/999999'))
    assert body['success'] is False
    assert body['message'] == 'Not found'


def test_history_filters_by_standard(client):
    client.post('/api/v1/compliance/check', json={'standard': 'dengbao'})
    client.post('/api/v1/compliance/check', json={'standard': 'cii'})
    assert len(_body(client.get('/api/v1/compliance/history'))['data']) == 2
    assert len(_body(client.get('/api/v1/compliance/history?standard=cii'))['data']) == 1
