"""自助门户单测：报障落单 + 概览行级隔离。"""
import pytest
from fastapi import HTTPException

from app.api.v1.portal import create_ticket, overview
from app.models import Contract, Customer, OrderReceive, SysRole, SysUser, SysUserRole, WorkOrder
from app.schemas.portal import PortalTicketCreate


def _mk_cust_user(db, name="A"):
    c = Customer(name=name)
    db.add(c)
    db.flush()
    role = SysRole(code="cust_service", name="客户服务", scope="customer")
    db.add(role)
    db.flush()
    u = SysUser(username=f"cust_{name}", name=f"客户{name}", pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id, customer_id=c.id))
    db.commit()
    return u, c


def test_create_ticket_customer_scoped(db):
    u, c = _mk_cust_user(db)
    body = PortalTicketCreate(description="系统无法登录", priority="高")
    data = create_ticket(body, user=u, db=db)["data"]

    wo = db.get(WorkOrder, data["work_order"]["id"])
    assert wo.description == "系统无法登录"
    assert wo.status == "待派单"
    assert wo.type == "客户工单"
    rec = db.get(OrderReceive, wo.receive_id)
    assert rec.customer_id == c.id  # 客户侧强制本人客户
    assert rec.source == "客户报障"


def test_create_ticket_platform_requires_customer(db):
    u = SysUser(username="admin", name="管理员", pwd_hash="x")
    db.add(u)
    db.commit()
    body = PortalTicketCreate(description="x")  # 平台侧未指定 customer_id
    with pytest.raises(HTTPException):
        create_ticket(body, user=u, db=db)


def test_overview_customer_isolation(db):
    u, ca = _mk_cust_user(db, name="A")
    cb = Customer(name="B")
    db.add(cb)
    db.flush()
    cta = Contract(customer_id=ca.id, name="A合同")
    ctb = Contract(customer_id=cb.id, name="B合同")
    db.add_all([cta, ctb])
    db.flush()
    db.add(WorkOrder(no="WO-2026-1001", type="客户工单", contract_id=cta.id, description="a"))
    db.add(WorkOrder(no="WO-2026-1002", type="客户工单", contract_id=ctb.id, description="b"))
    db.commit()

    data = overview(user=u, db=db)["data"]
    assert [c["name"] for c in data["contracts"]] == ["A合同"]
    assert data["work_order_status_counts"].get("待派单") == 1  # 仅本人客户工单
