"""行级隔离单测（scope_filter / owning_customer_id / assert_scoped）。"""
import pytest
from fastapi import HTTPException

from app.core.deps import assert_scoped, owning_customer_id, scope_filter
from app.models import Contract, Customer


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
