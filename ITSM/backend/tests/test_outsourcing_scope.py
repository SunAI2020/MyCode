"""外包账号隔离单测：外包仅见/操作自己被指派的任务。"""
import pytest
from fastapi import HTTPException

from app.api.v1.outsourcing import (
    accept_outsourcing,
    create_report,
    list_outsourcings,
    reject_outsourcing,
)
from app.models import Outsourcing, OutsourceUser, SysRole, SysUser, SysUserRole
from app.schemas.outsourcing import OutsourcingReportCreate


def _mk_user(db, username, role_code, name):
    role = db.query(SysRole).filter_by(code=role_code).first()
    if role is None:
        role = SysRole(code=role_code, name=name, scope="platform")
        db.add(role)
        db.flush()
    u = SysUser(username=username, name=name, pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id))
    db.commit()
    return u


def _mk_outsource_user(db, username, name):
    u = _mk_user(db, username, "outsource", name)
    ou = OutsourceUser(name=name, org="X单位", user_id=u.id)
    db.add(ou)
    db.commit()
    return u, ou


def test_outsource_sees_only_own(db):
    admin = _mk_user(db, "admin", "ticket_mgr", "管理员")
    os1, ou1 = _mk_outsource_user(db, "os1", "外包A")
    os2, ou2 = _mk_outsource_user(db, "os2", "外包B")
    o1 = Outsourcing(work_order_id=1, outsource_user_id=ou1.id, status="待接单")
    o2 = Outsourcing(work_order_id=1, outsource_user_id=ou2.id, status="待接单")
    db.add_all([o1, o2])
    db.commit()

    data = list_outsourcings(work_order_id=None, page=1, size=20, user=os1, db=db)["data"]
    assert [i["id"] for i in data["items"]] == [o1.id]  # 仅自己的任务


def test_platform_sees_all(db):
    admin = _mk_user(db, "admin", "ticket_mgr", "管理员")
    os1, ou1 = _mk_outsource_user(db, "os1", "外包A")
    o1 = Outsourcing(work_order_id=1, outsource_user_id=ou1.id, status="待接单")
    db.add(o1)
    db.commit()

    data = list_outsourcings(work_order_id=None, page=1, size=20, user=admin, db=db)["data"]
    assert len(data["items"]) == 1  # 平台见全部


def test_outsource_accept_own(db):
    os1, ou1 = _mk_outsource_user(db, "os1", "外包A")
    o1 = Outsourcing(work_order_id=1, outsource_user_id=ou1.id, status="待接单")
    db.add(o1)
    db.commit()

    data = accept_outsourcing(o1.id, user=os1, db=db)["data"]
    assert data["status"] == "已接单"


def test_outsource_reject_own(db):
    os1, ou1 = _mk_outsource_user(db, "os1", "外包A")
    o1 = Outsourcing(work_order_id=1, outsource_user_id=ou1.id, status="待接单")
    db.add(o1)
    db.commit()

    data = reject_outsourcing(o1.id, user=os1, db=db)["data"]
    assert data["status"] == "已拒单"


def test_outsource_cannot_accept_other(db):
    os1, ou1 = _mk_outsource_user(db, "os1", "外包A")
    os2, ou2 = _mk_outsource_user(db, "os2", "外包B")
    o2 = Outsourcing(work_order_id=1, outsource_user_id=ou2.id, status="待接单")
    db.add(o2)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        accept_outsourcing(o2.id, user=os1, db=db)
    assert exc.value.status_code == 403


def test_outsource_report_only_own(db):
    os1, ou1 = _mk_outsource_user(db, "os1", "外包A")
    os2, ou2 = _mk_outsource_user(db, "os2", "外包B")
    o2 = Outsourcing(work_order_id=1, outsource_user_id=ou2.id, status="已接单")
    db.add(o2)
    db.commit()

    body = OutsourcingReportCreate(outsourcing_id=o2.id, report_date="2026-09-26", progress="进展")
    with pytest.raises(HTTPException) as exc:
        create_report(body, user=os1, db=db)
    assert exc.value.status_code == 403
