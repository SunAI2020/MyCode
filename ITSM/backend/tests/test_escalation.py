"""SLA 升级记录单测：超时工单生成升级记录 + 去重。"""
from datetime import date, datetime, timedelta

from app.models import CmdbCi, Contract, ContractItem, Customer, Escalation, SlaPolicy, WorkOrder
from app.services.sla_service import scan_sla_escalations


def _mk_overdue_wo(db):
    c = Customer(name="A")
    db.add(c)
    db.flush()
    ct = Contract(customer_id=c.id, name="x")
    db.add(ct)
    db.flush()
    policy = SlaPolicy(
        name="金牌", customer_level="金牌", response_limit="15分钟",
        resolve_limit="4小时", escalation_chain="执行人→经理→负责人",
    )
    db.add(policy)
    db.flush()
    ci = CmdbCi(customer_id=c.id, contract_id=ct.id, name="CI")
    db.add(ci)
    db.flush()
    item = ContractItem(contract_id=ct.id, ci_id=ci.id, project="OA", sla_policy_id=policy.id)
    db.add(item)
    db.flush()
    wo = WorkOrder(
        no="WO-2026-9999", type="客户工单", contract_item_id=item.id,
        status="执行中", sla_deadline=datetime.now() - timedelta(days=2),
    )
    db.add(wo)
    db.commit()
    return wo


def test_scan_sla_escalations(db):
    wo = _mk_overdue_wo(db)
    n = scan_sla_escalations(db, today=date.today())
    assert n == 1
    esc = db.query(Escalation).filter_by(work_order_id=wo.id).first()
    assert esc.level == "红"
    assert esc.from_user == "执行人"
    assert esc.to_user == "经理"


def test_scan_sla_escalations_idempotent(db):
    wo = _mk_overdue_wo(db)
    scan_sla_escalations(db, today=date.today())
    n2 = scan_sla_escalations(db, today=date.today())  # 再次扫描不重复
    assert n2 == 0
    assert db.query(Escalation).filter_by(work_order_id=wo.id).count() == 1


def test_scan_skips_completed_work_order(db):
    wo = _mk_overdue_wo(db)
    wo.status = "已结单"
    db.commit()
    assert scan_sla_escalations(db, today=date.today()) == 0
