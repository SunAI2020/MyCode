"""行级隔离单测（scope_filter / owning_customer_id / assert_scoped）。"""
import pytest
from fastapi import HTTPException

from app.core.deps import assert_scoped, owning_customer_id, scope_filter
from app.models import Contract, ContractItem, Customer, OrderReceive, WorkOrder


def test_scope_filter_customer(db):
    c1 = Customer(name="A")
    c2 = Customer(name="B")
    db.add_all([c1, c2])
    db.commit()
    q = scope_filter(db.query(Customer), Customer, c1.id)
    rows = q.all()
    assert len(rows) == 1
    assert rows[0].id == c1.id


def test_scope_filter_contract(db):
    c1 = Customer(name="A")
    c2 = Customer(name="B")
    db.add_all([c1, c2])
    db.commit()
    ct = Contract(customer_id=c1.id, name="x")
    db.add(ct)
    db.commit()
    q = scope_filter(db.query(Contract), Contract, c1.id)
    assert [r.id for r in q.all()] == [ct.id]


def test_owning_customer_id_customer(db):
    c = Customer(name="A")
    db.add(c)
    db.commit()
    assert owning_customer_id(c, db) == c.id


def test_assert_scoped_customer(db):
    c = Customer(name="A")
    db.add(c)
    db.commit()
    assert_scoped(c, c.id, db)  # 不抛
    with pytest.raises(HTTPException):
        assert_scoped(c, c.id + 999, db)  # 越权 → 404


def test_owning_customer_id_via_receive(db):
    c = Customer(name="A")
    db.add(c)
    db.commit()
    rec = OrderReceive(customer_id=c.id)
    db.add(rec)
    db.commit()
    wo = WorkOrder(no="WO-2026-0101", type="客户工单", receive_id=rec.id, contract_id=None)
    db.add(wo)
    db.commit()
    assert owning_customer_id(wo, db) == c.id


def test_scope_filter_work_order_null_contract_via_receive(db):
    c1 = Customer(name="A")
    c2 = Customer(name="B")
    db.add_all([c1, c2])
    db.commit()
    rec1 = OrderReceive(customer_id=c1.id)
    rec2 = OrderReceive(customer_id=c2.id)
    db.add_all([rec1, rec2])
    db.commit()
    wo1 = WorkOrder(no="WO-2026-0201", type="客户工单", receive_id=rec1.id, contract_id=None)
    wo2 = WorkOrder(no="WO-2026-0202", type="客户工单", receive_id=rec2.id, contract_id=None)
    db.add_all([wo1, wo2])
    db.commit()
    q = scope_filter(db.query(WorkOrder), WorkOrder, c1.id)
    assert [r.id for r in q.all()] == [wo1.id]


def test_owning_customer_id_via_contract_item(db):
    c = Customer(name="A")
    db.add(c)
    db.commit()
    ct = Contract(customer_id=c.id, name="x")
    db.add(ct)
    db.flush()
    item = ContractItem(contract_id=ct.id, project="OA")
    db.add(item)
    db.commit()
    wo = WorkOrder(no="WO-2026-0301", type="客户工单", contract_item_id=item.id, contract_id=None)
    db.add(wo)
    db.commit()
    assert owning_customer_id(wo, db) == c.id


def test_scope_filter_work_order_via_contract_item(db):
    c1 = Customer(name="A")
    c2 = Customer(name="B")
    db.add_all([c1, c2])
    db.commit()
    ct1 = Contract(customer_id=c1.id, name="A合同")
    ct2 = Contract(customer_id=c2.id, name="B合同")
    db.add_all([ct1, ct2])
    db.flush()
    item1 = ContractItem(contract_id=ct1.id, project="OA")
    item2 = ContractItem(contract_id=ct2.id, project="ERP")
    db.add_all([item1, item2])
    db.commit()
    wo1 = WorkOrder(no="WO-2026-0401", type="客户工单", contract_item_id=item1.id, contract_id=None)
    wo2 = WorkOrder(no="WO-2026-0402", type="客户工单", contract_item_id=item2.id, contract_id=None)
    db.add_all([wo1, wo2])
    db.commit()
    q = scope_filter(db.query(WorkOrder), WorkOrder, c1.id)
    assert [r.id for r in q.all()] == [wo1.id]
