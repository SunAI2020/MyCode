"""内部任务单测：工单补 task_type/deadline 字段，内部任务完整下发。"""
from datetime import datetime, timezone

from app.api.v1.work_orders import create_work_order
from app.models import SysUser, WorkOrder
from app.schemas.work_order import WorkOrderCreate


def test_create_internal_task(db):
    u = SysUser(username="mgr", name="管理", pwd_hash="x")
    db.add(u)
    db.commit()

    deadline = datetime(2026, 12, 31, 12, 0, tzinfo=timezone.utc)
    data = create_work_order(
        WorkOrderCreate(type="内部任务", task_type="内部研发", deadline=deadline, description="开发巡检工具"),
        user=u,
        db=db,
    )["data"]
    assert data["type"] == "内部任务"
    assert data["task_type"] == "内部研发"
    assert data["description"] == "开发巡检工具"

    wo = db.get(WorkOrder, data["id"])
    assert wo.deadline is not None  # 截止时间已落库


def test_client_work_order_without_task_type(db):
    u = SysUser(username="mgr", name="管理", pwd_hash="x")
    db.add(u)
    db.commit()

    data = create_work_order(WorkOrderCreate(type="客户工单"), user=u, db=db)["data"]
    assert data["task_type"] is None  # 客户工单不填任务类型
