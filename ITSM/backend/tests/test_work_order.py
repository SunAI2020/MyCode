"""工单 schema 序列化单测：description 字段完整性。"""
from app.models import WorkOrder
from app.schemas.work_order import WorkOrderOut


def test_work_order_out_includes_description(db):
    wo = WorkOrder(no="WO-2026-0001", type="客户工单", status="待派单", description="系统无法登录")
    db.add(wo)
    db.commit()
    data = WorkOrderOut.model_validate(wo).model_dump()
    assert data["description"] == "系统无法登录"


def test_work_order_out_description_none(db):
    wo = WorkOrder(no="WO-2026-0002", type="客户工单", status="待派单")
    db.add(wo)
    db.commit()
    data = WorkOrderOut.model_validate(wo).model_dump()
    assert data["description"] is None
