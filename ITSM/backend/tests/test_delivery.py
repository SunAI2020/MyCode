"""项目交付单测（归属解析/行级隔离锚点）。"""
from app.core.deps import owning_customer_id
from app.models import Contract, Customer, Delivery


def test_delivery_owning_customer(db):
    c = Customer(name="A")
    db.add(c)
    db.commit()
    ct = Contract(customer_id=c.id, name="年度运维合同")
    db.add(ct)
    db.commit()
    d = Delivery(contract_id=ct.id, title="验收报告", report_type="验收报告")
    db.add(d)
    db.commit()
    assert owning_customer_id(d, db) == c.id
    assert d.sign == "未签署"
