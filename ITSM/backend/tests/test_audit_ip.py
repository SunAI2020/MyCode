"""审计 IP 留痕单测：record 自动填充客户端 IP。"""
from app.core.context import client_ip
from app.models import SysAuditLog
from app.services.audit_service import record


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
