"""定期工单幂等单测（对应 §9.2：季度频率到点只生成 1 次）。"""
from datetime import date, timedelta

from app.models import CmdbCi, Contract, ContractItem, ServiceCycle, WorkOrder
from app.scheduler.jobs import run_daily_work_order_generation


def test_generation_idempotent(db):
    today = date(2024, 3, 1)
    # 合同工期从今天开始，子项 1 次/季度 → 首期今天到点
    c = Contract(customer_id=1, name="c", start_date=today, end_date=today + timedelta(days=200))
    db.add(c)
    db.flush()
    ci = CmdbCi(customer_id=1, contract_id=c.id, name="CI")
    db.add(ci)
    db.flush()
    item = ContractItem(contract_id=c.id, ci_id=ci.id, project="漏洞扫描", frequency=1, unit="quarter")
    db.add(item)
    db.commit()

    # 第一次运行：应生成恰好 1 个工期 + 1 个工单（今天到点的那一期）
    n1 = run_daily_work_order_generation(db, today=today)
    assert n1 == 1
    assert db.query(ServiceCycle).count() == 1
    assert db.query(WorkOrder).count() == 1

    # 第二次运行：幂等，不再生成
    n2 = run_daily_work_order_generation(db, today=today)
    assert n2 == 0
    assert db.query(ServiceCycle).count() == 1
    assert db.query(WorkOrder).count() == 1
