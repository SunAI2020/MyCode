"""合同履约洞察单测：临近到期 + 履约缺口。"""
from datetime import date, timedelta

from app.models import CmdbCi, Contract, ContractItem, Customer, ServiceCycle
from app.services.ai_service import contract_insight


def _mk_item(db):
    c = Customer(name="A")
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name="x", start_date=date(2026, 1, 1), end_date=date(2027, 1, 1))
    db.add(ct)
    db.flush()
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name="CI")
    db.add(ci)
    db.flush()
    item = ContractItem(contract_id=ct.id, ci_id=ci.id, project="OA", frequency=1, unit="月")
    db.add(item)
    db.commit()
    return item


def test_contract_insight_near_expiry(db):
    item = _mk_item(db)
    today = date(2026, 9, 26)
    db.add(
        ServiceCycle(
            contract_item_id=item.id, cycle_no=1, service_start=today,
            service_end=today + timedelta(days=3), status="started", auto_generated=True,
        )
    )
    db.commit()

    insights = contract_insight(db, today=today)
    assert any(i["type"] == "临近到期" and i["item_id"] == item.id for i in insights)


def test_contract_insight_gap(db):
    item = _mk_item(db)  # 无任何工期 → 应生成 12 个但已生成 0
    insights = contract_insight(db, today=date(2026, 9, 26))
    gaps = [i for i in insights if i["type"] == "履约缺口" and i["item_id"] == item.id]
    assert gaps
    assert gaps[0]["gap"] == 12
