"""客户自助门户：自助报障 + 概览（合同履约 / 工单进度 / 交付报告）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import customer_scope_of, get_current_user, get_db, require_role, scope_filter
from app.models import CmdbCi, Contract, ContractItem, Delivery, OrderReceive, SysUser, WorkOrder
from app.schemas.portal import PortalTicketCreate
from app.schemas.work_order import WorkOrderOut
from app.services.audit_service import record
from app.utils.response import ok
from app.utils.wo_no import next_work_order_no

PORTAL_ROLE = ("sys_admin", "sys_ops", "ticket_mgr", "cust_admin", "cust_service")

router = APIRouter(prefix="/portal", tags=["自助门户"])


@router.post("/tickets")
def create_ticket(
    body: PortalTicketCreate,
    user: SysUser = Depends(require_role(*PORTAL_ROLE)),
    db: Session = Depends(get_db),
):
    """自助报障：落接单（客户报障）+ 工单（待派单）。客户侧强制本人客户，平台侧须指定客户。"""
    scope = customer_scope_of(user, db)
    if scope is not None:
        customer_id = scope
    else:
        if body.customer_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "平台侧报障须指定 customer_id")
        customer_id = body.customer_id
    # 客户侧行级隔离：合同 / 合同子项 / 配置项均须归属本人客户，防跨租户引用
    if scope is not None:
        if body.contract_id is not None:
            c = db.get(Contract, body.contract_id)
            if c is None or c.customer_id != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户报障")
        if body.contract_item_id is not None:
            item = db.get(ContractItem, body.contract_item_id)
            owner = db.get(Contract, item.contract_id) if item else None
            if owner is None or owner.customer_id != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权引用其他客户的合同子项")
        if body.ci_id is not None:
            ci = db.get(CmdbCi, body.ci_id)
            if ci is None or ci.customer_id != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权引用其他客户的配置项")

    rec = OrderReceive(
        source="客户报障",
        customer_id=customer_id,
        contract_id=body.contract_id,
        contract_item_id=body.contract_item_id,
        ci_id=body.ci_id,
        project=body.project,
        contact=body.contact,
    )
    db.add(rec)
    db.flush()
    wo = WorkOrder(
        no=next_work_order_no(db),
        type="客户工单",
        receive_id=rec.id,
        contract_id=body.contract_id,
        contract_item_id=body.contract_item_id,
        ci_id=body.ci_id,
        project=body.project,
        priority=body.priority,
        description=body.description,
    )
    db.add(wo)
    db.flush()
    record(db, user_id=user.id, action="create_ticket", resource=f"work_order:{wo.id}", after=str(body.model_dump()))
    db.commit()
    return ok({"receive_id": rec.id, "work_order": WorkOrderOut.model_validate(wo).model_dump()})


@router.get("/overview")
def overview(user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """门户概览：本人客户合同 / 工单状态计数 / 最近工单 / 最近交付（行级隔离）。"""
    scope = customer_scope_of(user, db)
    contracts = scope_filter(db.query(Contract), Contract, scope).all()
    wo_q = scope_filter(db.query(WorkOrder), WorkOrder, scope)
    status_counts = dict(
        wo_q.with_entities(WorkOrder.status, func.count(WorkOrder.id))
        .group_by(WorkOrder.status)
        .all()
    )
    recent_wo = wo_q.order_by(WorkOrder.created_at.desc()).limit(10).all()
    del_q = scope_filter(db.query(Delivery), Delivery, scope)
    recent_del = del_q.order_by(Delivery.created_at.desc()).limit(10).all()
    return ok(
        {
            "contracts": [{"id": c.id, "name": c.name, "status": c.status} for c in contracts],
            "work_order_status_counts": status_counts,
            "recent_work_orders": [WorkOrderOut.model_validate(w).model_dump() for w in recent_wo],
            "recent_deliveries": [
                {"id": d.id, "title": d.title, "report_type": d.report_type, "sign": d.sign}
                for d in recent_del
            ],
        }
    )
