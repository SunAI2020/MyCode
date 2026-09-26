"""审计 IP 留痕单测：record 自动填充客户端 IP。"""
from types import SimpleNamespace

from app.core.config import settings
from app.core.context import client_ip
from app.core.deps import _client_ip
from app.models import SysAuditLog
from app.services.audit_service import record


def _req(headers=None, host="9.9.9.9"):
    return SimpleNamespace(
        headers=dict(headers or {}),
        client=SimpleNamespace(host=host),
    )


def test_client_ip_trusts_x_real_ip_when_proxy_trusted(monkeypatch):
    # 生产置于 nginx 之后（TRUST_PROXY_HEADERS=true）时，采用 X-Real-IP
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    req = _req(headers={"x-real-ip": "1.2.3.4"}, host="172.17.0.2")
    assert _client_ip(req) == "1.2.3.4"


def test_client_ip_ignores_x_real_ip_when_untrusted():
    # 默认不信任反代头，直连暴露下客户端伪造 X-Real-IP 无效
    req = _req(headers={"x-real-ip": "6.6.6.6"}, host="192.168.1.50")
    assert _client_ip(req) == "192.168.1.50"


def test_client_ip_ignores_spoofable_xff():
    # X-Forwarded-For 可被客户端伪造，恒不采信；回退到直连对端
    req = _req(headers={"x-forwarded-for": "6.6.6.6"}, host="192.168.1.50")
    assert _client_ip(req) == "192.168.1.50"


def test_client_ip_falls_back_to_peer():
    assert _client_ip(_req(host="192.168.1.50")) == "192.168.1.50"


def test_client_ip_none_request():
    assert _client_ip(None) is None


def test_record_auto_fills_ip_from_context(db):
    token = client_ip.set("192.168.1.100")
    try:
        record(db, user_id=1, action="update", resource="work_order:1")
        db.flush()
        log = db.query(SysAuditLog).filter_by(action="update").first()
        assert log.ip == "192.168.1.100"
    finally:
        client_ip.reset(token)


def test_record_explicit_ip_overrides(db):
    record(db, user_id=1, action="create", resource="x", ip="10.0.0.1")
    db.flush()
    log = db.query(SysAuditLog).filter_by(action="create").first()
    assert log.ip == "10.0.0.1"


def test_record_default_ip_none_when_no_context(db):
    record(db, user_id=1, action="delete", resource="x")
    db.flush()
    log = db.query(SysAuditLog).filter_by(action="delete").first()
    assert log.ip is None
