"""工单聚合模型单测：多业务系统 / 多服务类别 / 多频次聚合创建。"""
from datetime import date

import pytest
from fastapi import HTTPException

from app.api.v1.work_orders import create_aggregate_work_order
from app.core.deps import scope_filter
from app.models import (
    CmdbCi,
    Contract,
    ContractItem,
    Customer,
    SysRole,
    SysUser,
    SysUserRole,
    WorkOrder,
    WorkOrderCi,
    WorkOrderCycle,
    WorkOrderItem,
)
from app.schemas.work_order import AggregateCycleIn, AggregateWorkOrderCreate


def _mk_user(db):
    u = SysUser(username="admin", name="管理员", pwd_hash="x")
    db.add(u)
    db.commit()
    return u


def _mk_chain(db, cname):
    c = Customer(name=cname)
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name=f"{cname}合同", start_date=date(2026, 1, 1), end_date=date(2027, 1, 1))
    db.add(ct)
    db.flush()
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name=f"{cname}系统")
    db.add(ci)
    db.flush()
    item = ContractItem(contract_id=ct.id, ci_id=ci.id, project="漏洞扫描", frequency=1, unit="月")
    db.add(item)
    db.commit()
    return c, ci, item


def test_create_aggregate_work_order(db):
    u = _mk_user(db)
    c, ci, item = _mk_chain(db, "A")
    body = AggregateWorkOrderCreate(
        customer_id=c.id,
        ci_ids=[ci.id],
        contract_item_ids=[item.id],
        cycles=[AggregateCycleIn(contract_item_id=item.id, cycle_no=1)],
    )
    data = create_aggregate_work_order(body, user=u, db=db)["data"]
    wo = db.get(WorkOrder, data["id"])
    assert wo.customer_id == c.id
    assert wo.status == "待派单"
    assert db.query(WorkOrderCi).filter_by(work_order_id=wo.id).count() == 1
    assert db.query(WorkOrderItem).filter_by(work_order_id=wo.id).count() == 1
    cycles = db.query(WorkOrderCycle).filter_by(work_order_id=wo.id).all()
    assert len(cycles) == 1
    assert cycles[0].cycle_no == 1
    assert cycles[0].service_start == date(2026, 1, 1)
    assert cycles[0].service_end == date(2026, 2, 1)


def test_create_aggregate_rejects_cross_customer_ci(db):
    u = _mk_user(db)
    c, ci, item = _mk_chain(db, "A")
    _, ci2, _ = _mk_chain(db, "B")
    body = AggregateWorkOrderCreate(customer_id=c.id, ci_ids=[ci2.id], contract_item_ids=[], cycles=[])
    with pytest.raises(HTTPException) as exc:
        create_aggregate_work_order(body, user=u, db=db)
    assert exc.value.status_code == 400


def test_create_aggregate_rejects_mismatch_item(db):
    u = _mk_user(db)
    c, ci, item = _mk_chain(db, "A")
    _, _, item2 = _mk_chain(db, "B")
    body = AggregateWorkOrderCreate(customer_id=c.id, ci_ids=[ci.id], contract_item_ids=[item2.id], cycles=[])
    with pytest.raises(HTTPException) as exc:
        create_aggregate_work_order(body, user=u, db=db)
    assert exc.value.status_code == 400


def test_create_aggregate_rejects_invalid_cycle_no(db):
    u = _mk_user(db)
    c, ci, item = _mk_chain(db, "A")  # 1 次/月、12 个月 → 12 个工期
    body = AggregateWorkOrderCreate(
        customer_id=c.id, ci_ids=[ci.id], contract_item_ids=[item.id],
        cycles=[AggregateCycleIn(contract_item_id=item.id, cycle_no=99)],
    )
    with pytest.raises(HTTPException) as exc:
        create_aggregate_work_order(body, user=u, db=db)
    assert exc.value.status_code == 400


def test_create_aggregate_rejects_out_of_scope_customer(db):
    c, ci, item = _mk_chain(db, "A")
    c2, _, _ = _mk_chain(db, "B")
    role = SysRole(code="ticket_mgr", name="工单管理", scope="platform")
    db.add(role)
    db.flush()
    u = SysUser(username="mgr", name="工单", pwd_hash="x")
    db.add(u)
    db.flush()
    db.add(SysUserRole(user_id=u.id, role_id=role.id, customer_id=c.id))  # 绑定到客户 A
    db.commit()
    body = AggregateWorkOrderCreate(customer_id=c2.id, ci_ids=[], contract_item_ids=[], cycles=[])
    with pytest.raises(HTTPException) as exc:
        create_aggregate_work_order(body, user=u, db=db)
    assert exc.value.status_code == 403


def test_scope_filter_aggregate_by_customer(db):
    u = _mk_user(db)
    c, ci, item = _mk_chain(db, "A")
    c2, ci2, item2 = _mk_chain(db, "B")
    body = AggregateWorkOrderCreate(
        customer_id=c.id, ci_ids=[ci.id], contract_item_ids=[item.id],
        cycles=[AggregateCycleIn(contract_item_id=item.id, cycle_no=1)],
    )
    wid = create_aggregate_work_order(body, user=u, db=db)["data"]["id"]
    body2 = AggregateWorkOrderCreate(
        customer_id=c2.id, ci_ids=[ci2.id], contract_item_ids=[item2.id],
        cycles=[AggregateCycleIn(contract_item_id=item2.id, cycle_no=1)],
    )
    wid2 = create_aggregate_work_order(body2, user=u, db=db)["data"]["id"]
    q = scope_filter(db.query(WorkOrder), WorkOrder, c.id)
    ids = {r.id for r in q.all()}
    assert wid in ids
    assert wid2 not in ids
