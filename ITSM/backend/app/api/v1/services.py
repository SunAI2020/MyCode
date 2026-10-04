"""SLA 策略 CRUD + 服务工期/提醒（读）。工期拆分/预警在步骤五。"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_role
from app.models import (
    CmdbCi,
    Contract,
    ContractItem,
    Customer,
    ServiceCycle,
    ServiceReminder,
    SlaPolicy,
    SysUser,
    WorkOrder,
    WorkOrderAssignee,
    WorkOrderCycle,
)
from app.schemas.service import (
    CycleRemindIn,
    ServiceCycleOut,
    ServiceCycleUpdate,
    ServiceReminderOut,
    SlaPolicyCreate,
    SlaPolicyOut,
    SlaPolicyUpdate,
)
from app.services.audit_service import record
from app.services.notify_service import notify_all_channels
from app.utils.pagination import paginate
from app.utils.response import ok

READ_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

sla = APIRouter(prefix="/sla-policies", tags=["SLA 策略"])
cycles = APIRouter(prefix="/cycles", tags=["服务工期"])
reminders = APIRouter(prefix="/reminders", tags=["服务提醒"])


# ---- SLA 策略 ----
@sla.get("")
def list_policies(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    return ok(paginate(db.query(SlaPolicy), page, size, SlaPolicyOut))


@sla.post("")
def create_policy(
    body: SlaPolicyCreate,
    user: SysUser = Depends(require_permission("sla:write")),
    db: Session = Depends(get_db),
):
    obj = SlaPolicy(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"sla_policy:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(SlaPolicyOut.model_validate(obj).model_dump())


@sla.get("/{pid}")
def get_policy(pid: int, user: SysUser = Depends(require_role(*READ_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(SlaPolicy, pid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA 策略不存在")
    return ok(SlaPolicyOut.model_validate(obj).model_dump())


@sla.put("/{pid}")
def update_policy(
    pid: int,
    body: SlaPolicyUpdate,
    user: SysUser = Depends(require_permission("sla:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(SlaPolicy, pid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA 策略不存在")
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"sla_policy:{pid}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(SlaPolicyOut.model_validate(obj).model_dump())


@sla.delete("/{pid}")
def delete_policy(pid: int, user: SysUser = Depends(require_permission("sla:delete")), db: Session = Depends(get_db)):
    obj = db.get(SlaPolicy, pid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SLA 策略不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"sla_policy:{pid}")
    db.commit()
    return ok({"deleted": pid})


# ---- 服务工期（读；生成在步骤五） ----
@cycles.get("")
def list_cycles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    expiring: bool = Query(False, description="仅返回已到期/即将到期（未来 7 天）的工期"),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(ServiceCycle)
    if expiring:
        q = q.filter(
            ServiceCycle.status.notin_(["done", "cancelled"]),
            ServiceCycle.service_end <= date.today() + timedelta(days=7),
        ).order_by(ServiceCycle.service_end.asc())
    else:
        q = q.order_by(ServiceCycle.id.desc())
    data = paginate(q, page, size, ServiceCycleOut)
    # 富化 客户名称 / 项目名称 / 业务系统/ 服务类别
    item_ids = [it["contract_item_id"] for it in data["items"]]
    if item_ids:
        rows = (
            db.query(
                ContractItem.id,
                Contract.name,
                Customer.name,
                CmdbCi.name,
                ContractItem.project,
            )
            .join(Contract, ContractItem.contract_id == Contract.id)
            .join(Customer, Contract.customer_id == Customer.id)
            .outerjoin(CmdbCi, ContractItem.ci_id == CmdbCi.id)
            .filter(ContractItem.id.in_(item_ids))
            .all()
        )
        m = {r[0]: r for r in rows}
        for it in data["items"]:
            r = m.get(it["contract_item_id"])
            if r is not None:
                it["project_name"] = r[1]
                it["customer_name"] = r[2]
                it["ci_name"] = r[3]
                it["item_project"] = r[4]
    return ok(data)


@cycles.put("/{cid}")
def update_cycle(
    cid: int,
    body: ServiceCycleUpdate,
    user: SysUser = Depends(require_permission("sla:write")),
    db: Session = Depends(get_db),
):
    obj = db.get(ServiceCycle, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工期不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    return ok(ServiceCycleOut.model_validate(obj).model_dump())


@cycles.delete("/{cid}")
def delete_cycle(
    cid: int,
    user: SysUser = Depends(require_permission("sla:delete")),
    db: Session = Depends(get_db),
):
    obj = db.get(ServiceCycle, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工期不存在")
    db.delete(obj)
    db.commit()
    return ok({"deleted": cid})


def _work_order_for_cycle(db: Session, cycle: ServiceCycle) -> WorkOrder | None:
    """定位该工期对应的工单：优先简单工单(contract_item_id + current_cycle_no)，其次聚合工单(work_order_cycle)。"""
    wo = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.contract_item_id == cycle.contract_item_id,
            WorkOrder.current_cycle_no == cycle.cycle_no,
        )
        .first()
    )
    if wo is not None:
        return wo
    link = (
        db.query(WorkOrderCycle)
        .filter(
            WorkOrderCycle.contract_item_id == cycle.contract_item_id,
            WorkOrderCycle.cycle_no == cycle.cycle_no,
        )
        .first()
    )
    return db.get(WorkOrder, link.work_order_id) if link is not None else None


def _cycle_content(db: Session, cycle: ServiceCycle) -> str:
    """构造「客户 + 业务系统 + 期次」的提醒文案前缀。"""
    item = db.get(ContractItem, cycle.contract_item_id)
    contract = db.get(Contract, item.contract_id) if item else None
    customer = db.get(Customer, contract.customer_id) if contract else None
    ci = db.get(CmdbCi, item.ci_id) if item and item.ci_id else None
    name = f"{customer.name if customer else ''}的{ci.name if ci else ''}业务系统"
    return f"{name}第 {cycle.cycle_no} 次服务"


def _notify_work_order(db: Session, cycle: ServiceCycle, type_: str, level: str, content: str, require_wo: bool = True) -> None:
    """为工期对应工单发送提醒/催单：落到执行人并多渠道推送；require_wo=True 时无对应工单报错。"""
    wo = _work_order_for_cycle(db, cycle)
    if wo is None and require_wo:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该工期无对应工单，请尽快派单！")
    to_user_id = None
    if wo is not None:
        assignee = (
            db.query(WorkOrderAssignee.user_id)
            .filter(WorkOrderAssignee.work_order_id == wo.id, WorkOrderAssignee.is_active.is_(True))
            .first()
        )
        to_user_id = assignee[0] if assignee else None
    db.add(
        ServiceReminder(
            cycle_id=cycle.id,
            type=type_,
            level=level,
            content=content,
            to_user_id=to_user_id,
        )
    )
    db.commit()
    notify_all_channels(content)


@cycles.post("/{cid}/remind")
def remind_cycle(
    cid: int,
    body: CycleRemindIn | None = None,
    user: SysUser = Depends(require_permission("sla:write")),
    db: Session = Depends(get_db),
):
    cycle = db.get(ServiceCycle, cid)
    if cycle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工期不存在")
    content = (body.content.strip() if body and body.content and body.content.strip() else None) or (
        f"{_cycle_content(db, cycle)}，服务工期将于 {cycle.service_end} 结束，请及时处理"
    )
    _notify_work_order(db, cycle, "提醒", "黄", content, require_wo=False)
    return ok({"reminded": cid})


@cycles.post("/{cid}/urge")
def urge_cycle(
    cid: int,
    user: SysUser = Depends(require_permission("sla:write")),
    db: Session = Depends(get_db),
):
    cycle = db.get(ServiceCycle, cid)
    if cycle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工期不存在")
    content = f"{_cycle_content(db, cycle)}，服务工期将于 {cycle.service_end} 结束，请尽快完成"
    _notify_work_order(db, cycle, "催单", "红", content)
    return ok({"urged": cid})


@cycles.post("/{cid}/cancel")
def cancel_cycle(
    cid: int,
    user: SysUser = Depends(require_permission("sla:delete")),
    db: Session = Depends(get_db),
):
    cycle = db.get(ServiceCycle, cid)
    if cycle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工期不存在")
    cycle.status = "cancelled"
    db.commit()
    return ok({"cancelled": cid})


# ---- 服务提醒（读；生成在步骤五） ----
@reminders.get("")
def list_reminders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    return ok(paginate(db.query(ServiceReminder), page, size, ServiceReminderOut))
