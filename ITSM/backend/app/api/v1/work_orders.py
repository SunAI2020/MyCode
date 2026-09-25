"""接单 / 工单 / 派单 / 状态流转。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import (
    assert_scoped,
    customer_scope_of,
    get_current_user,
    get_db,
    require_role,
    scope_filter,
)
from app.models import OrderDispatch, OrderReceive, SysUser, WorkOrder, WorkOrderAssignee
from app.core.security import mask_sensitive, masked_page
from app.schemas.work_order import (
    AssigneeOut,
    DispatchCreate,
    DispatchOut,
    OrderReceiveCreate,
    OrderReceiveOut,
    TransferIn,
    WorkOrderCreate,
    WorkOrderOut,
    WorkOrderStatusUpdate,
)
from app.services.audit_service import record
from app.services.dispatch_service import transfer_assignee
from app.utils.pagination import paginate
from app.utils.response import ok
from app.utils.wo_no import next_work_order_no

WORK_WRITE_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

# 状态机：合法迁移表（旁路 已取消）
STATUS_TRANSITIONS = {
    "待派单": ["已派单", "已取消"],
    "已派单": ["计划中", "已取消"],
    "计划中": ["进行中", "已取消"],
    "进行中": ["待验收", "已关闭"],
    "待验收": ["已完成", "已关闭"],
    "已完成": ["已关闭"],
    "已关闭": [],
    "已取消": [],
}

receives = APIRouter(prefix="/receives", tags=["接单"])
router = APIRouter(prefix="/work-orders", tags=["工单"])


# ---- 接单 ----
@receives.get("")
def list_receives(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(OrderReceive), OrderReceive, scope)
    return ok(masked_page(paginate(q, page, size, OrderReceiveOut), scope))


@receives.post("")
def create_receive(
    body: OrderReceiveCreate,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    if scope is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建接单记录")
    obj = OrderReceive(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"order_receive:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(OrderReceiveOut.model_validate(obj).model_dump())


@receives.get("/{rid}")
def get_receive(rid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(OrderReceive, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "接单记录不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    return ok(mask_sensitive(OrderReceiveOut.model_validate(obj).model_dump(), scope))


# ---- 工单 ----
@router.get("")
def list_work_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(WorkOrder)
    q = scope_filter(q, WorkOrder, customer_scope_of(user, db))
    return ok(paginate(q, page, size, WorkOrderOut))


@router.post("")
def create_work_order(
    body: WorkOrderCreate,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    receive = None
    if body.receive_id is not None:
        receive = db.get(OrderReceive, body.receive_id)
        if receive is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "接单记录不存在")
        assert_scoped(receive, customer_scope_of(user, db), db)
    wo = WorkOrder(
        no=next_work_order_no(db),
        type=body.type,
        receive_id=body.receive_id,
        contract_id=body.contract_id if body.contract_id is not None else (receive.contract_id if receive else None),
        contract_item_id=body.contract_item_id if body.contract_item_id is not None else (receive.contract_item_id if receive else None),
        ci_id=body.ci_id if body.ci_id is not None else (receive.ci_id if receive else None),
        project=body.project if body.project is not None else (receive.project if receive else None),
        priority=body.priority,
    )
    db.add(wo)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"work_order:{wo.id}", after=str(body.model_dump()))
    db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.get("/{wid}")
def get_work_order(wid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.put("/{wid}/status")
def update_status(
    wid: int,
    body: WorkOrderStatusUpdate,
    user: SysUser = Depends(require_role("sys_admin", "sys_ops", "ticket_mgr", "cs_staff", "sec_staff")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    allowed = STATUS_TRANSITIONS.get(wo.status, [])
    if body.status != wo.status and body.status not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"非法状态流转：{wo.status} → {body.status}")
    before = wo.status
    wo.status = body.status
    if body.progress is not None:
        wo.progress = body.progress
    db.flush()
    record(db, user_id=user.id, action="update_status", resource=f"work_order:{wid}", before=before, after=body.status)
    db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.post("/{wid}/dispatch")
def dispatch(
    wid: int,
    body: DispatchCreate,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    if wo.status != "待派单":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"当前状态「{wo.status}」不可派单（仅待派单可派单）")
    for a in db.query(WorkOrderAssignee).filter_by(work_order_id=wid, is_active=True).all():
        a.is_active = False  # 停用旧活跃执行人，防重复派单累计
    total = sum(a.workload_ratio for a in body.assignees)
    if abs(total - 100) > 0.01:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "执行人工作量比例合计须为 100%")

    disp = OrderDispatch(
        work_order_id=wid,
        dispatch_type=body.dispatch_type,
        dispatch_price=body.dispatch_price,
        service_start=body.service_start,
        service_end=body.service_end,
        accept_standard=body.accept_standard,
        suggest_reason=body.suggest_reason,
    )
    db.add(disp)
    db.flush()
    assignees = []
    for a in body.assignees:
        assignees.append(WorkOrderAssignee(work_order_id=wid, user_id=a.user_id, workload_ratio=a.workload_ratio))
    db.add_all(assignees)
    wo.dispatch_id = disp.id
    wo.status = "已派单"
    db.flush()
    record(db, user_id=user.id, action="dispatch", resource=f"work_order:{wid}", after=str(body.model_dump()))
    db.commit()
    return ok({
        "dispatch": DispatchOut.model_validate(disp).model_dump(),
        "assignees": [AssigneeOut.model_validate(a).model_dump() for a in assignees],
        "work_order": WorkOrderOut.model_validate(wo).model_dump(),
    })


@router.post("/{wid}/assignees/transfer")
def transfer(
    wid: int,
    body: TransferIn,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    try:
        new = transfer_assignee(db, wid, body.from_user_id, body.to_user_id, body.actual_hours)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="transfer", resource=f"work_order:{wid}", after=str(body.model_dump()))
    db.commit()
    return ok(AssigneeOut.model_validate(new).model_dump())
