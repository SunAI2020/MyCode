"""接单 / 工单 / 派单 / 状态流转。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import (
    assert_scoped,
    customer_scope_of,
    get_current_user,
    get_db,
    require_permission,
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
    Report,
    ServiceCycle,
    ServiceReminder,
    SysRole,
    SysUser,
    SysUserRole,
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
    AssigneeIn,
    AssigneeOut,
    DispatchCreate,
    DispatchOut,
    OrderReceiveCreate,
    OrderReceiveOut,
    TransferIn,
    WorkOrderAggregateEditIn,
    WorkOrderCreate,
    WorkOrderEditIn,
    WorkOrderOut,
    WorkOrderStatusUpdate,
    WorkOrderUpdate,
)
from app.schemas.kb import KbArticleOut
from app.services.audit_service import record
from app.services.cycle_service import split_cycles
from app.services.ai_service import summarize_work_order, work_order_to_kb_draft
from app.services.dispatch_service import record_assignee_hours, transfer_assignee
from app.services.evidence_service import collect_for_work_order
from app.services.search_service import index_kb_article
from app.services.workflow_service import assert_transition, log_transition
from app.utils.pagination import paginate
from app.utils.response import ok
from app.utils.wo_no import next_work_order_no, work_order_no_scope

receives = APIRouter(prefix="/receives", tags=["接单"])
router = APIRouter(prefix="/work-orders", tags=["工单"])


def _assert_dispatchable(db: Session, user_ids: list[int]) -> None:
    """执行人仅限我方服务人员 + 外包人员（platform 角色），排除客户方/第三方。"""
    uids = {uid for uid in user_ids if uid is not None}
    if not uids:
        return
    platform_ids = {
        uid
        for uid, scope in (
            db.query(SysUserRole.user_id, SysRole.scope)
            .join(SysRole, SysUserRole.role_id == SysRole.id)
            .filter(SysUserRole.user_id.in_(uids), SysRole.scope == "platform")
            .all()
        )
    }
    bad = [uid for uid in uids if uid not in platform_ids]
    if bad:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "执行人仅限我方服务人员或外包人员")


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
    user: SysUser = Depends(require_permission("work_order:write")),
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
    contract_item_id: int | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(WorkOrder)
    q = scope_filter(q, WorkOrder, customer_scope_of(user, db))
    if contract_item_id is not None:
        # 同时匹配简单工单（contract_item_id 直挂）与聚合工单（经 WorkOrderItem 关联）
        wo_ids = db.query(WorkOrderItem.work_order_id).filter(WorkOrderItem.contract_item_id == contract_item_id)
        q = q.filter(or_(WorkOrder.contract_item_id == contract_item_id, WorkOrder.id.in_(wo_ids)))
    q = q.order_by(WorkOrder.id.desc())
    data = paginate(q, page, size, WorkOrderOut)
    # 补齐客户：简单工单 customer_id 为空（历史/调度器生成）时从合同反推，保证列表客户列有值
    _miss = [it["contract_id"] for it in data["items"] if not it.get("customer_id") and it.get("contract_id")]
    if _miss:
        _cmap = dict(db.query(Contract.id, Contract.customer_id).filter(Contract.id.in_(_miss)).all())
        for it in data["items"]:
            if not it.get("customer_id") and it.get("contract_id"):
                it["customer_id"] = _cmap.get(it["contract_id"])
    # 富化执行人姓名（work_order_assignee → sys_user.name）+ 服务类别（聚合工单经 WorkOrderItem → ContractItem.project）
    ids = [it["id"] for it in data["items"]]
    if ids:
        rows = (
            db.query(WorkOrderAssignee.work_order_id, SysUser.name)
            .join(SysUser, WorkOrderAssignee.user_id == SysUser.id)
            .filter(WorkOrderAssignee.work_order_id.in_(ids), WorkOrderAssignee.is_active.is_(True))
            .all()
        )
        names: dict[int, list[str]] = {}
        for wid, name in rows:
            names.setdefault(wid, []).append(name)

        # 聚合工单的服务类别：project 为空，经 WorkOrderItem 关联 ContractItem，多类别顿号连接
        item_rows = (
            db.query(WorkOrderItem.work_order_id, ContractItem.project)
            .join(ContractItem, WorkOrderItem.contract_item_id == ContractItem.id)
            .filter(WorkOrderItem.work_order_id.in_(ids))
            .all()
        )
        proj_map: dict[int, list[str]] = {}
        for wid, proj in item_rows:
            proj_map.setdefault(wid, [])
            if proj and proj not in proj_map[wid]:
                proj_map[wid].append(proj)

        # 简单工单：有 contract_item_id 时，服务类别以 ContractItem.project 实时为准（改名即时生效）
        simple_ids = [
            it["contract_item_id"]
            for it in data["items"]
            if it.get("contract_item_id") and it["id"] not in proj_map
        ]
        ci_proj: dict[int, str] = {}
        if simple_ids:
            ci_proj = {
                cid: proj
                for cid, proj in db.query(ContractItem.id, ContractItem.project)
                .filter(ContractItem.id.in_(simple_ids))
                .all()
            }

        for it in data["items"]:
            it["assignee_names"] = names.get(it["id"], [])
            if it["id"] in proj_map:
                it["project"] = "、".join(proj_map[it["id"]])
            elif it.get("contract_item_id"):
                it["project"] = ci_proj.get(it["contract_item_id"], it.get("project") or "")

        # 是否已提交过报告（「提交报告/更新报告」按钮切换）
        reported_ids = {
            wid
            for wid, in db.query(Report.work_order_id).filter(Report.work_order_id.in_(ids)).all()
        }
        for it in data["items"]:
            it["has_report"] = it["id"] in reported_ids
    return ok(data)


@router.post("")
def create_work_order(
    body: WorkOrderCreate,
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    receive = None
    if body.receive_id is not None:
        receive = db.get(OrderReceive, body.receive_id)
        if receive is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "接单记录不存在")
        assert_scoped(receive, customer_scope_of(user, db), db)
    if body.generate_cycle:
        if body.contract_item_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "「同时生成工期」需选择服务类别")
        if body.service_start is None or body.service_end is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "勾选「同时生成工期」需填写服务开始/结束时间")
    eff_contract_id = body.contract_id if body.contract_id is not None else (receive.contract_id if receive else None)
    customer_id = None
    if eff_contract_id is not None:
        _c = db.get(Contract, eff_contract_id)
        customer_id = _c.customer_id if _c else None
    # 重复检测：同一子项 + 同一起止时间已有工单 → 返回 duplicate 标志（按日期判重，cycle_no 兜底）
    if body.generate_cycle and body.service_start is not None and body.service_end is not None:
        dup_id = (
            db.query(WorkOrder.id)
            .join(
                ServiceCycle,
                (ServiceCycle.contract_item_id == WorkOrder.contract_item_id)
                & (ServiceCycle.cycle_no == WorkOrder.current_cycle_no),
            )
            .filter(
                WorkOrder.contract_item_id == body.contract_item_id,
                ServiceCycle.service_start == body.service_start,
                ServiceCycle.service_end == body.service_end,
            )
            .first()
        )
        if dup_id is None and body.cycle_no is not None:
            dup_id = db.query(WorkOrder.id).filter_by(
                contract_item_id=body.contract_item_id, current_cycle_no=body.cycle_no
            ).first()
        if dup_id is not None:
            item = db.get(ContractItem, body.contract_item_id)
            contract = db.get(Contract, eff_contract_id) if eff_contract_id else (db.get(Contract, item.contract_id) if item else None)
            customer = db.get(Customer, contract.customer_id) if contract else None
            ci = db.get(CmdbCi, body.ci_id) if body.ci_id else (db.get(CmdbCi, item.ci_id) if item else None)
            project = body.project or (item.project if item else None)
            msg = (
                f"{customer.name if customer else ''}客户"
                f"{contract.name if contract else ''}项目"
                f"{ci.name if ci else ''}业务系统，"
                f"{body.service_start}-{body.service_end}时间的"
                f"{project or ''}服务类别工单已经存在，请勿重复生成！"
            )
            return ok({"duplicate": True, "message": msg})
    with work_order_no_scope(db):
        wo = WorkOrder(
            no=next_work_order_no(db),
            type=body.type,
            receive_id=body.receive_id,
            customer_id=customer_id,
            contract_id=eff_contract_id,
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
        # 同时生成工期：按 preview 选中的期次回填 current_cycle_no（复用已存在工期或新建）
        if body.generate_cycle:
            cycle_no = body.cycle_no
            if cycle_no is not None:
                cycle = db.query(ServiceCycle).filter_by(contract_item_id=body.contract_item_id, cycle_no=cycle_no).first()
                if cycle is None:
                    cycle = ServiceCycle(
                        contract_item_id=body.contract_item_id, cycle_no=cycle_no,
                        service_start=body.service_start, service_end=body.service_end,
                        status="pending", auto_generated=False,
                    )
                    db.add(cycle)
                else:
                    cycle.service_start = body.service_start
                    cycle.service_end = body.service_end
            else:
                max_no = (
                    db.query(ServiceCycle.cycle_no)
                    .filter(ServiceCycle.contract_item_id == body.contract_item_id)
                    .order_by(ServiceCycle.cycle_no.desc())
                    .first()
                )
                cycle = ServiceCycle(
                    contract_item_id=body.contract_item_id,
                    cycle_no=(max_no[0] + 1) if max_no else 1,
                    service_start=body.service_start, service_end=body.service_end,
                    status="pending", auto_generated=False,
                )
                db.add(cycle)
            db.flush()
            wo.current_cycle_no = cycle.cycle_no
        # 同时派单：直接落派单 + 执行人，工单置为待执行
        if body.dispatch and body.assignee_id is not None:
            _assert_dispatchable(db, [body.assignee_id])
            disp = OrderDispatch(
                work_order_id=wo.id,
                dispatch_type=body.dispatch_type,
                service_start=body.service_start,
                service_end=body.service_end,
            )
            db.add(disp)
            db.flush()
            db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=body.assignee_id, workload_ratio=100))
            wo.dispatch_id = disp.id
            wo.status = "待执行"
            log_transition(db, entity="work_order", entity_id=wo.id, from_status="待派单", to_status="待执行", operator_id=user.id)
        record(db, user_id=user.id, action="create", resource=f"work_order:{wo.id}", after=str(body.model_dump()))
        db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


def _item_cycles(db: Session, item: ContractItem) -> list[tuple[int, date, date]]:
    """按合同起止日期 + 服务类别频率/单位即时拆分频次（工期），与 generate_cycles 同源。"""
    contract = db.get(Contract, item.contract_id)
    if contract is None or contract.start_date is None or contract.end_date is None:
        return []
    return split_cycles(contract.start_date, contract.end_date, item.frequency, item.unit)


@router.post("/aggregate/preview")
def aggregate_cycles_preview(
    body: AggregatePreviewIn,
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    """给定服务类别列表，返回各项目的频次（工期）列表，供前端渲染复选。"""
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
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该服务类别")
        item_cycles = _item_cycles(db, item)
        worked = {
            no for (no,) in db.query(WorkOrder.current_cycle_no)
            .filter(WorkOrder.contract_item_id == item.id, WorkOrder.current_cycle_no.isnot(None))
            .all()
        }
        worked |= {
            no for (no,) in db.query(WorkOrderCycle.cycle_no)
            .filter(WorkOrderCycle.contract_item_id == item.id)
            .all()
        }
        cycles[iid] = [
            {"cycle_no": no, "service_start": s.isoformat(), "service_end": e.isoformat(), "has_work_order": no in worked}
            for no, s, e in item_cycles
        ]
    return ok({"cycles": cycles})


@router.post("/aggregate")
def create_aggregate_work_order(
    body: AggregateWorkOrderCreate,
    user: SysUser = Depends(require_permission("work_order:write")),
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
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "业务系统不存在或不属于该客户")
        ci_set.add(ci_id)

    items_by_id: dict[int, ContractItem] = {}
    for iid in body.contract_item_ids:
        item = db.get(ContractItem, iid)
        if item is None or item.ci_id not in ci_set:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "服务类别不存在或不属于所选业务系统")
        items_by_id[iid] = item

    item_cycle_dates: dict[int, dict[int, tuple[date, date]]] = {}
    for iid, item in items_by_id.items():
        item_cycle_dates[iid] = {no: (s, e) for no, s, e in _item_cycles(db, item)}

    cycle_rows: list[tuple[int, int, date, date]] = []
    seen: set[tuple[int, int]] = set()
    for c in body.cycles:
        dates = item_cycle_dates.get(c.contract_item_id)
        if dates is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "频次不属于所选服务类别")
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
            if body.generate_cycle and not db.query(ServiceCycle.id).filter_by(contract_item_id=iid, cycle_no=no).first():
                db.add(ServiceCycle(contract_item_id=iid, cycle_no=no, service_start=s, service_end=e, status="pending", auto_generated=False))
        if body.dispatch:
            assignees = body.assignees
            if not assignees and body.assignee_id is not None:
                assignees = [AssigneeIn(user_id=body.assignee_id, workload_ratio=100)]
            if assignees:
                _assert_dispatchable(db, [a.user_id for a in assignees])
                disp = OrderDispatch(work_order_id=wo.id, dispatch_type=body.dispatch_type, service_start=body.service_start, service_end=body.service_end)
                db.add(disp)
                db.flush()
                for a in assignees:
                    db.add(WorkOrderAssignee(work_order_id=wo.id, user_id=a.user_id, workload_ratio=a.workload_ratio))
                wo.dispatch_id = disp.id
                wo.status = "待执行"
                log_transition(db, entity="work_order", entity_id=wo.id, from_status="待派单", to_status="待执行", operator_id=user.id)
        record(db, user_id=user.id, action="create_aggregate", resource=f"work_order:{wo.id}", after=str(body.model_dump()))
        db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.get("/{wid}/scope")
def get_work_order_scope(wid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """聚合工单明细：业务系统 / 服务类别 / 频次。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    cis = []
    for r in db.query(WorkOrderCi).filter_by(work_order_id=wid).all():
        ci = db.get(CmdbCi, r.ci_id)
        if ci:
            cis.append({"ci_id": ci.id, "name": ci.name, "type": ci.type})
    # 简单工单：无 WorkOrderCi，直接按 ci_id 补业务系统
    if not cis and wo.ci_id is not None:
        ci = db.get(CmdbCi, wo.ci_id)
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
    item_map = {it["contract_item_id"]: it for it in items}
    ci_map = {c["ci_id"]: c["name"] for c in cis}
    cycles = []
    for r in db.query(WorkOrderCycle).filter_by(work_order_id=wid).all():
        it = item_map.get(r.contract_item_id)
        cycles.append({
            "contract_item_id": r.contract_item_id,
            "cycle_no": r.cycle_no,
            "service_start": r.service_start.isoformat(),
            "service_end": r.service_end.isoformat(),
            "project": it["project"] if it else "",
            "ci_name": ci_map.get(it["ci_id"], "") if it and it.get("ci_id") else "",
        })
    # 简单工单：无 WorkOrderCycle，按 current_cycle_no 补当前工期
    if not cycles and wo.contract_item_id is not None and wo.current_cycle_no is not None:
        cyc = db.query(ServiceCycle).filter_by(contract_item_id=wo.contract_item_id, cycle_no=wo.current_cycle_no).first()
        if cyc:
            item = db.get(ContractItem, wo.contract_item_id)
            cycles.append({
                "contract_item_id": wo.contract_item_id,
                "cycle_no": cyc.cycle_no,
                "service_start": cyc.service_start.isoformat(),
                "service_end": cyc.service_end.isoformat(),
                "project": item.project if item else "",
                "ci_name": ci_map.get(wo.ci_id, "") if wo.ci_id else "",
            })
    # 当前执行人（多执行人 + 占比，编辑弹窗回填用）+ 派单类型
    assignees = []
    for a in db.query(WorkOrderAssignee).filter_by(work_order_id=wid, is_active=True).all():
        assignees.append({"user_id": a.user_id, "workload_ratio": float(a.workload_ratio)})
    dispatch_type = None
    if wo.dispatch_id is not None:
        _disp = db.get(OrderDispatch, wo.dispatch_id)
        if _disp is not None:
            dispatch_type = _disp.dispatch_type
    # 项目名称：优先工单直挂合同，否则取首个服务子项的合同
    contract_name = ""
    _contract_id = wo.contract_id
    if _contract_id is None and items:
        _item = db.get(ContractItem, items[0]["contract_item_id"])
        if _item is not None:
            _contract_id = _item.contract_id
    if _contract_id is not None:
        _contract = db.get(Contract, _contract_id)
        if _contract is not None:
            contract_name = _contract.name
    return ok({
        "work_order": WorkOrderOut.model_validate(wo).model_dump(),
        "cis": cis, "items": items, "cycles": cycles,
        "contract_name": contract_name,
        "assignee_id": assignees[0]["user_id"] if assignees else None,
        "assignees": assignees,
        "dispatch_type": dispatch_type,
    })


@router.get("/{wid}")
def get_work_order(wid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.put("/{wid}")
def update_work_order(
    wid: int,
    body: WorkOrderUpdate,
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    if wo.status == "已关闭":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已关闭工单仅保留记录，不可编辑")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(wo, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"work_order:{wid}", after=str(data))
    db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.put("/{wid}/edit")
def edit_work_order(
    wid: int,
    body: WorkOrderEditIn,
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    if wo.status == "已关闭":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已关闭工单仅保留记录，不可编辑")
    if body.type is not None:
        wo.type = body.type
    if body.priority is not None:
        wo.priority = body.priority
    if body.description is not None:
        wo.description = body.description
    # 更新工期日期
    if body.service_start is not None and body.service_end is not None and wo.contract_item_id is not None and wo.current_cycle_no is not None:
        cycle = db.query(ServiceCycle).filter_by(contract_item_id=wo.contract_item_id, cycle_no=wo.current_cycle_no).first()
        if cycle is not None:
            cycle.service_start = body.service_start
            cycle.service_end = body.service_end
    # 重新派单
    if body.dispatch and body.assignee_id is not None:
        _assert_dispatchable(db, [body.assignee_id])
        for a in db.query(WorkOrderAssignee).filter_by(work_order_id=wid, is_active=True).all():
            a.is_active = False
        disp = OrderDispatch(
            work_order_id=wid,
            dispatch_type=body.dispatch_type or "内部",
            service_start=body.service_start,
            service_end=body.service_end,
        )
        db.add(disp)
        db.flush()
        db.add(WorkOrderAssignee(work_order_id=wid, user_id=body.assignee_id, workload_ratio=100))
        wo.dispatch_id = disp.id
        if wo.status == "待派单":
            wo.status = "待执行"
            log_transition(db, entity="work_order", entity_id=wid, from_status="待派单", to_status="待执行", operator_id=user.id)
    db.flush()
    record(db, user_id=user.id, action="edit", resource=f"work_order:{wid}", after=str(body.model_dump()))
    db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.put("/{wid}/aggregate")
def edit_aggregate_work_order(
    wid: int,
    body: WorkOrderAggregateEditIn,
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    """编辑聚合工单：重选业务系统、改优先级/起止时间、重新生成工期、重新派单。服务类别固定。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(wo, scope, db)
    if wo.status == "已关闭":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "已关闭工单仅保留记录，不可编辑")

    if body.priority is not None:
        wo.priority = body.priority
    if body.type is not None:
        wo.type = body.type

    # 重选业务系统（校验非空 + 业务系统归属，防跨客户越权）
    if not body.ci_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请至少选择一个业务系统")
    db.query(WorkOrderCi).filter_by(work_order_id=wid).delete()
    for ci_id in body.ci_ids:
        ci = db.get(CmdbCi, ci_id)
        if ci is None or ci.customer_id != wo.customer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "业务系统不存在或不属于该客户")
        db.add(WorkOrderCi(work_order_id=wid, ci_id=ci_id))

    # 重新生成工期：删除原工期（频次快照 + 服务工期），按新起止重新拆分
    if body.regenerate_cycle and body.service_start is not None and body.service_end is not None:
        old_cycles = db.query(WorkOrderCycle).filter_by(work_order_id=wid).all()
        for c in old_cycles:
            sc = db.query(ServiceCycle).filter_by(contract_item_id=c.contract_item_id, cycle_no=c.cycle_no).first()
            # 仅删除本工单自建（auto_generated=False）的服务工期，避免误删调度生成/他单共享的工期
            if sc is not None and sc.auto_generated is False:
                db.query(ServiceReminder).filter_by(cycle_id=sc.id).delete()
                db.delete(sc)
        db.query(WorkOrderCycle).filter_by(work_order_id=wid).delete()
        for (iid,) in db.query(WorkOrderItem.contract_item_id).filter_by(work_order_id=wid).all():
            item = db.get(ContractItem, iid)
            if item is None:
                continue
            for no, s, e in split_cycles(body.service_start, body.service_end, item.frequency, item.unit):
                db.add(WorkOrderCycle(work_order_id=wid, contract_item_id=iid, cycle_no=no, service_start=s, service_end=e))
                if not db.query(ServiceCycle.id).filter_by(contract_item_id=iid, cycle_no=no).first():
                    db.add(ServiceCycle(contract_item_id=iid, cycle_no=no, service_start=s, service_end=e, status="pending", auto_generated=False))

    # 重新派单：删除原派单记录 + 执行人，重新落派单
    if body.dispatch:
        assignees = body.assignees
        if not assignees and body.assignee_id is not None:
            assignees = [AssigneeIn(user_id=body.assignee_id, workload_ratio=100)]
        if not assignees:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "重新派单需选择执行人")
        _assert_dispatchable(db, [a.user_id for a in assignees])
        db.query(WorkOrderAssignee).filter_by(work_order_id=wid).delete()
        db.query(OrderDispatch).filter_by(work_order_id=wid).delete()
        disp = OrderDispatch(
            work_order_id=wid,
            dispatch_type=body.dispatch_type,
            service_start=body.service_start,
            service_end=body.service_end,
        )
        db.add(disp)
        db.flush()
        for a in assignees:
            db.add(WorkOrderAssignee(work_order_id=wid, user_id=a.user_id, workload_ratio=a.workload_ratio))
        wo.dispatch_id = disp.id
        if wo.status == "待派单":
            wo.status = "待执行"
            log_transition(db, entity="work_order", entity_id=wid, from_status="待派单", to_status="待执行", operator_id=user.id)

    db.flush()
    record(db, user_id=user.id, action="edit_aggregate", resource=f"work_order:{wid}", after=str(body.model_dump()))
    db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.delete("/{wid}")
def delete_work_order(
    wid: int,
    delete_cycles: bool = Query(True, description="是否同步删除与该工单关联的服务工期"),
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(wo, scope, db)
    # 收集工单关联的服务工期键：简单工单 → current_cycle_no；聚合工单 → work_order_cycle
    cycle_keys: list[tuple[int, int]] = []
    if wo.contract_item_id is not None and wo.current_cycle_no is not None:
        cycle_keys.append((wo.contract_item_id, wo.current_cycle_no))
    for iid, no in db.query(WorkOrderCycle.contract_item_id, WorkOrderCycle.cycle_no).filter_by(work_order_id=wid).all():
        cycle_keys.append((iid, no))
    # 删除工单自身关联（执行人/聚合业务系统/服务类别/频次/派单）
    db.query(WorkOrderAssignee).filter_by(work_order_id=wid).delete()
    db.query(WorkOrderCi).filter_by(work_order_id=wid).delete()
    db.query(WorkOrderItem).filter_by(work_order_id=wid).delete()
    db.query(WorkOrderCycle).filter_by(work_order_id=wid).delete()
    db.query(OrderDispatch).filter_by(work_order_id=wid).delete()
    # 同步删除关联服务工期（默认勾选；逐条作用域校验 + 清理其提醒记录避免外键残留）
    if delete_cycles:
        for iid, no in cycle_keys:
            cycle = db.query(ServiceCycle).filter_by(contract_item_id=iid, cycle_no=no).first()
            if cycle is None:
                continue
            assert_scoped(cycle, scope, db)
            db.query(ServiceReminder).filter_by(cycle_id=cycle.id).delete()
            db.delete(cycle)
    try:
        db.delete(wo)
        record(db, user_id=user.id, action="delete", resource=f"work_order:{wid}")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "该工单仍有关联数据（安全隐患/绩效/外包/变更/交付/升级等），无法删除",
        ) from None
    return ok({"deleted": wid})


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
    # 合规证据自动采集：工单完成 → 匹配服务类别对应合规要求生成证据（步骤 51）
    if body.status == "已结单":
        collect_for_work_order(db, wo, operator_id=user.id)
    db.flush()
    record(db, user_id=user.id, action="update_status", resource=f"work_order:{wid}", before=before, after=body.status)
    db.commit()
    return ok(WorkOrderOut.model_validate(wo).model_dump())


@router.post("/{wid}/dispatch")
def dispatch(
    wid: int,
    body: DispatchCreate,
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    if wo.status != "待派单":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"当前状态「{wo.status}」不可派单（仅待派单可派单）")
    if body.type is not None:
        wo.type = body.type
    _assert_dispatchable(db, [a.user_id for a in body.assignees])
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
    wo.status = "待执行"
    log_transition(
        db,
        entity="work_order",
        entity_id=wid,
        from_status="待派单",
        to_status="待执行",
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
    user: SysUser = Depends(require_permission("work_order:write")),
    db: Session = Depends(get_db),
):
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    _assert_dispatchable(db, [body.to_user_id])
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
    user: SysUser = Depends(require_permission("work_order:write")),
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
def summarize(wid: int, user: SysUser = Depends(require_permission("work_order:write")), db: Session = Depends(get_db)):
    """工单执行摘要（AI 生成，无 LLM 时降级模板摘要）。"""
    wo = db.get(WorkOrder, wid)
    if wo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工单不存在")
    assert_scoped(wo, customer_scope_of(user, db), db)
    return ok({"summary": summarize_work_order(wo)})


@router.post("/{wid}/to-kb")
def to_kb(wid: int, user: SysUser = Depends(require_permission("work_order:write")), db: Session = Depends(get_db)):
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
