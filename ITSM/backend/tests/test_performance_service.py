"""绩效考核单测：公式 + 换岗分摊精确归属。"""
from app.models import OrderDispatch, Performance, WorkOrder, WorkOrderAssignee
from app.services.performance_service import compute_perf_score, generate_performance


def test_compute_perf_score():
    # 10 × 100 × 0.6 × 1.0 × 1.0 = 600
    assert compute_perf_score(10, 100, 60, 1.0, 1.0) == 600.0
    # 600 × 1.2 × 0.8 = 576
    assert compute_perf_score(10, 100, 60, 1.2, 0.8) == 576.0


def test_generate_performance_60_40(db):
    wo = WorkOrder(no="WO-2026-0001", type="客户工单", status="已完成")
    db.add(wo)
    db.flush()
    db.add(OrderDispatch(work_order_id=wo.id, dispatch_price=1000))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=1, workload_ratio=60, actual_hours=10, is_active=True))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=2, workload_ratio=40, actual_hours=5, is_active=False))
    db.commit()

    n = generate_performance(db, wo.id)
    assert n == 2

    rows = db.query(Performance).filter_by(work_order_id=wo.id).all()
    by_user = {r.user_id: float(r.perf_score) for r in rows}
    # 换岗分摊精确归属：A 10h×1000×0.6=6000；B 5h×1000×0.4=2000
    assert by_user[1] == 6000.0
    assert by_user[2] == 2000.0


def test_generate_performance_idempotent(db):
    wo = WorkOrder(no="WO-2026-0002", type="客户工单", status="已完成")
    db.add(wo)
    db.flush()
    db.add(OrderDispatch(work_order_id=wo.id, dispatch_price=500))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=1, workload_ratio=100, actual_hours=8, is_active=True))
    db.commit()

    generate_performance(db, wo.id)
    generate_performance(db, wo.id)  # 幂等：删除重建，不累积
    assert db.query(Performance).filter_by(work_order_id=wo.id).count() == 1
