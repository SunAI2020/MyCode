"""SLA 策略 CRUD + 服务周期/提醒（读）。周期拆分/预警在步骤五。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permission, require_role
from app.models import CmdbCi, Contract, ContractItem, Customer, ServiceCycle, ServiceReminder, SlaPolicy, SysUser
from app.schemas.service import (
    ServiceCycleOut,
    ServiceReminderOut,
    SlaPolicyCreate,
    SlaPolicyOut,
    SlaPolicyUpdate,
)
from app.services.audit_service import record
from app.utils.pagination import paginate
from app.utils.response import ok

READ_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

sla = APIRouter(prefix="/sla-policies", tags=["SLA 策略"])
cycles = APIRouter(prefix="/cycles", tags=["服务周期"])
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


# ---- 服务周期（读；生成在步骤五） ----
@cycles.get("")
def list_cycles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    data = paginate(db.query(ServiceCycle).order_by(ServiceCycle.id.desc()), page, size, ServiceCycleOut)
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


# ---- 服务提醒（读；生成在步骤五） ----
@reminders.get("")
def list_reminders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*READ_ROLE)),
    db: Session = Depends(get_db),
):
    return ok(paginate(db.query(ServiceReminder), page, size, ServiceReminderOut))
