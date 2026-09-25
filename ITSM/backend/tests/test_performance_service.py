"""绩效考核单测：公式 + 换岗分摊精确归属。"""
from app.models import OrderDispatch, Performance, WorkOrder, WorkOrderAssignee
from app.services.dispatch_service import record_assignee_hours, transfer_assignee
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


def test_generate_performance_after_transfer(db):
    """换岗后：旧执行人按已工时×原比例、新执行人按续接工时×原比例，精确归属且不双计。"""
    wo = WorkOrder(no="WO-2026-0003", type="客户工单", status="已完成")
    db.add(wo)
    db.flush()
    db.add(OrderDispatch(work_order_id=wo.id, dispatch_price=1000))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=1, workload_ratio=60, actual_hours=None, is_active=True))
    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=2, workload_ratio=40, actual_hours=5, is_active=False))
    db.commit()

    transfer_assignee(db, wo.id, from_user_id=1, to_user_id=3, actual_hours=8.5)
    record_assignee_hours(db, wo.id, 3, actual_hours=6.5)
    db.commit()

    generate_performance(db, wo.id)
    by_user = {r.user_id: float(r.perf_score) for r in db.query(Performance).filter_by(work_order_id=wo.id).all()}
    # 用户1 8.5h×60%=5100；用户3 续接 6.5h×60%=3900；用户2 5h×40%=2000
    assert by_user[1] == 5100.0
    assert by_user[3] == 3900.0
    assert by_user[2] == 2000.0
