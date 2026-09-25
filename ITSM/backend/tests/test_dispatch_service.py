"""换岗分摊单测（对应 §9.2：60/40 精确归属）。"""
from app.models import WorkOrder, WorkOrderAssignee
from app.services.dispatch_service import record_assignee_hours, transfer_assignee


def _mk_wo(db, no="WO-2026-0001"):
    wo = WorkOrder(no=no, type="客户工单")
    db.add(wo)
    db.flush()
    return wo


def test_transfer_60_40(db):
    wo = _mk_wo(db)
    a = WorkOrderAssignee(work_order_id=wo.id, user_id=1, workload_ratio=60, is_active=True)
    b = WorkOrderAssignee(work_order_id=wo.id, user_id=2, workload_ratio=40, is_active=True)
    db.add_all([a, b])
    db.commit()

    new = transfer_assignee(db, wo.id, from_user_id=1, to_user_id=3, actual_hours=8.5)
    db.commit()

    # 旧执行人离岗
    assert a.is_active is False
    assert a.actual_hours == 8.5
    assert a.ended_at is not None
    # 新执行人续接，继承 60
    assert new.user_id == 3
    assert float(new.workload_ratio) == 60.0
    assert new.is_active is True
    # active 比例合计 100（60 + 40）
    active = db.query(WorkOrderAssignee).filter_by(work_order_id=wo.id, is_active=True).all()
    assert sum(float(x.workload_ratio) for x in active) == 100.0


def test_transfer_missing_assignee_raises(db):
    wo = _mk_wo(db, "WO-2026-0002")
    db.commit()
    try:
        transfer_assignee(db, wo.id, from_user_id=99, to_user_id=3)
        assert False, "应抛 ValueError"
    except ValueError as e:
        assert "不存在或已离岗" in str(e)


def test_record_assignee_hours(db):
    wo = _mk_wo(db, "WO-2026-0003")
    a = WorkOrderAssignee(work_order_id=wo.id, user_id=1, workload_ratio=100, is_active=True)
    db.add(a)
    db.commit()

    a2 = record_assignee_hours(db, wo.id, 1, actual_hours=7.5, complete=True)
    db.commit()

    assert float(a2.actual_hours) == 7.5
    assert a2.is_active is False
    assert a2.ended_at is not None


def test_record_assignee_hours_missing_raises(db):
    wo = _mk_wo(db, "WO-2026-0004")
    db.commit()
    try:
        record_assignee_hours(db, wo.id, 99, actual_hours=1.0)
        assert False, "应抛 ValueError"
    except ValueError as e:
        assert "不存在或已离岗" in str(e)
