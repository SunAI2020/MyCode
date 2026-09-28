"""接单 / 工单 / 派单 / 状态流转。"""
from datetime import date

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
from app.models import (
    CmdbCi,
    Contract,
    ContractItem,
    Customer,
    OrderDispatch,
    OrderReceive,
    SysUser,
    WorkOrder,
    WorkOrderAssignee,
    WorkOrderCi,
    WorkOrderCycle,
    WorkOrderItem,
)
from app.core.security import mask_sensitive, masked_page
from app.schemas.work_order import (
    AggregatePreviewIn,
    AggregateWorkOrderCreate,
    AssigneeHoursIn,
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
from app.schemas.kb import KbArticleOut
from app.services.audit_service import record
from app.services.cycle_service import split_cycles
from app.services.ai_service import summarize_work_order, work_order_to_kb_draft
from app.services.dispatch_service import record_assignee_hours, transfer_assignee
from app.services.search_service import index_kb_article
from app.services.workflow_service import assert_transition, log_transition
from app.utils.pagination import paginate
from app.utils.response import ok
from app.utils.wo_no import next_work_order_no, work_order_no_scope

WORK_WRITE_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

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
    with work_order_no_scope(db):
        wo = WorkOrder(
            no=next_work_order_no(db),
            type=body.type,
            receive_id=body.receive_id,
            contract_id=body.contract_id if body.contract_id is not None else (receive.contract_id if receive else None),
            contract_item_id=body.contract_item_id if body.contract_item_id is not None else (receive.contract_item_id if receive else None),
            ci_id=body.ci_id if body.ci_id is not None else (receive.ci_id if receive else None),
            project=body.project if body.project is not None else (receive.project if receive else None),
            priority=body.priority,
            description=body.description,
            task_type=body.task_type,
            deadline=body.deadline,
        )
        db.add(wo)
        db.flush()
        record(db, user_id=user.id, action="create", resource=f"work_order:{wo.id}", after=str(body.model_dump()))
        db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


def _item_cycles(db: Session, item: ContractItem) -> list[tuple[int, date, date]]:
    """按合同起止日期 + 服务项目频率/单位即时拆分频次（周期），与 generate_cycles 同源。"""
    contract = db.get(Contract, item.contract_id)
    if contract is None or contract.start_date is None or contract.end_date is None:
        return []
    return split_cycles(contract.start_date, contract.end_date, item.frequency, item.unit)


@router.post("/aggregate/preview")
def aggregate_cycles_preview(
    body: AggregatePreviewIn,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    """给定服务项目列表，返回各项目的频次（周期）列表，供前端渲染复选。"""
    scope = customer_scope_of(user, db)
    cycles: dict[int, list[dict]] = {}
    for iid in body.contract_item_ids:
        item = db.get(ContractItem, iid)
        if item is None:
            cycles[iid] = []
            continue
        if scope is not None:
            ci = db.get(CmdbCi, item.ci_id)
            if ci is None or ci.customer_id != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该服务项目")
        cycles[iid] = [
            {"cycle_no": no, "service_start": s.isoformat(), "service_end": e.isoformat()}
            for no, s, e in _item_cycles(db, item)
        ]
    return ok({"cycles": cycles})


@router.post("/aggregate")
def create_aggregate_work_order(
    body: AggregateWorkOrderCreate,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    customer = db.get(Customer, body.customer_id)
    if customer is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "客户不存在")
    scope = customer_scope_of(user, db)
    if scope is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建工单")

    ci_set: set[int] = set()
    for ci_id in body.ci_ids:
        ci = db.get(CmdbCi, ci_id)
        if ci is None or ci.customer_id != body.customer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "服务对象不存在或不属于该客户")
        ci_set.add(ci_id)

    items_by_id: dict[int, ContractItem] = {}
    for iid in body.contract_item_ids:
        item = db.get(ContractItem, iid)
        if item is None or item.ci_id not in ci_set:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "服务项目不存在或不属于所选服务对象")
        items_by_id[iid] = item

    item_cycle_dates: dict[int, dict[int, tuple[date, date]]] = {}
    for iid, item in items_by_id.items():
        item_cycle_dates[iid] = {no: (s, e) for no, s, e in _item_cycles(db, item)}

    cycle_rows: list[tuple[int, int, date, date]] = []
    seen: set[tuple[int, int]] = set()
    for c in body.cycles:
        dates = item_cycle_dates.get(c.contract_item_id)
        if dates is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "频次不属于所选服务项目")
        if c.cycle_no not in dates:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "频次编号无效")
        if (c.contract_item_id, c.cycle_no) in seen:
            continue
        seen.add((c.contract_item_id, c.cycle_no))
        s, e = dates[c.cycle_no]
        cycle_rows.append((c.contract_item_id, c.cycle_no, s, e))

    with work_order_no_scope(db):
        wo = WorkOrder(
            no=next_work_order_no(db),
            type=body.type,
            customer_id=body.customer_id,
            priority=body.priority,
            description=body.description,
            status="待派单",
        )
        db.add(wo)
        db.flush()
        for ci_id in body.ci_ids:
            db.add(WorkOrderCi(work_order_id=wo.id, ci_id=ci_id))
        for iid in body.contract_item_ids:
            db.add(WorkOrderItem(work_order_id=wo.id, contract_item_id=iid))
        for iid, no, s, e in cycle_rows:
            db.add(WorkOrderCycle(work_order_id=wo.id, contract_item_id=iid, cycle_no=no, service_start=s, service_end=e))
        record(db, user_id=user.id, action="create_aggregate", resource=f"work_order:{wo.id}", after=str(body.model_dump()))
        db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.get("/{wid}/scope")
def get_work_order_scope(wid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """聚合工单明细：服务对象 / 服务项目 / 频次。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    cis = []
    for r in db.query(WorkOrderCi).filter_by(work_order_id=wid).all():
        ci = db.get(CmdbCi, r.ci_id)
        if ci:
            cis.append({"ci_id": ci.id, "name": ci.name, "type": ci.type})
    items = []
    for r in db.query(WorkOrderItem).filter_by(work_order_id=wid).all():
        item = db.get(ContractItem, r.contract_item_id)
        if item:
            items.append({
                "contract_item_id": item.id, "ci_id": item.ci_id, "project": item.project,
                "frequency": item.frequency, "unit": item.unit, "price": item.price,
            })
    cycles = [
        {"contract_item_id": r.contract_item_id, "cycle_no": r.cycle_no,
         "service_start": r.service_start.isoformat(), "service_end": r.service_end.isoformat()}
        for r in db.query(WorkOrderCycle).filter_by(work_order_id=wid).all()
    ]
    return ok({"work_order": WorkOrderOut.model_validate(wo).model_dump(), "cis": cis, "items": items, "cycles": cycles})


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
    before = wo.status
    try:
        assert_transition(db, "work_order", wo.status, body.status)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    wo.status = body.status
    if body.progress is not None:
        wo.progress = body.progress
    if before != body.status:
        log_transition(
            db,
            entity="work_order",
            entity_id=wid,
            from_status=before,
            to_status=body.status,
            operator_id=user.id,
        )
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
    log_transition(
        db,
        entity="work_order",
        entity_id=wid,
        from_status="待派单",
        to_status="已派单",
        operator_id=user.id,
    )
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


@router.post("/{wid}/assignees/{uid}/hours")
def record_hours(
    wid: int,
    uid: int,
    body: AssigneeHoursIn,
    user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    """记录执行人实际工时（换岗后新执行人续接完成时回填），可选离岗。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    try:
        a = record_assignee_hours(db, wid, uid, body.actual_hours, body.complete)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="record_hours", resource=f"work_order:{wid}", after=str(body.model_dump()))
    db.commit()
    return ok(AssigneeOut.model_validate(a).model_dump())


@router.post("/{wid}/summary")
def summarize(wid: int, user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)), db: Session = Depends(get_db)):
    """工单执行摘要（AI 生成，无 LLM 时降级模板摘要）。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    return ok({"summary": summarize_work_order(wo)})


@router.post("/{wid}/to-kb")
def to_kb(wid: int, user: SysUser = Depends(require_role(*WORK_WRITE_ROLE)), db: Session = Depends(get_db)):
    """工单转知识草稿（status=草稿，审核后入库）。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    article = work_order_to_kb_draft(db, wo, user.id)
    record(db, user_id=user.id, action="to_kb", resource=f"work_order:{wid}", after=f"kb_article:{article.id}")
    db.commit()
    index_kb_article(article)  # 增量同步 ES
    return ok(KbArticleOut.model_validate(article).model_dump())
