"""项目交付 CRUD + 签署验收。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import (
    assert_scoped,
    customer_scope_of,
    get_current_user,
    get_db,
    owning_customer_id,
    require_role,
    scope_filter,
)
from app.models import Contract, Delivery, SysUser, WorkOrder
from app.schemas.delivery import DeliveryCreate, DeliveryOut, DeliveryUpdate
from app.services.audit_service import record
from app.utils.pagination import paginate
from app.utils.response import ok

WRITE_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")
SIGN_ROLE = ("sys_admin", "sys_ops", "ticket_mgr", "cust_admin", "cust_service")

router = APIRouter(prefix="/deliveries", tags=["项目交付"])


@router.get("")
def list_deliveries(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(Delivery), Delivery, scope)
    return ok(paginate(q, page, size, DeliveryOut))


@router.post("")
def create_delivery(
    body: DeliveryCreate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    # 防御纵深：校验合同与工单双归属（与 update_delivery 对称），防跨租户挂载交付
    if scope is not None:
        if body.contract_id is not None:
            c = db.get(Contract, body.contract_id)
            if c is None or c.customer_id != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建交付")
        if body.work_order_id is not None:
            wo = db.get(WorkOrder, body.work_order_id)
            if wo is None or owning_customer_id(wo, db) != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户工单创建交付")
    obj = Delivery(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"delivery:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(DeliveryOut.model_validate(obj).model_dump())


@router.get("/{did}")
def get_delivery(did: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(Delivery, did)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "交付不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    return ok(DeliveryOut.model_validate(obj).model_dump())


@router.put("/{did}")
def update_delivery(
    did: int,
    body: DeliveryUpdate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(Delivery, did)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "交付不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    # 防御纵深：校验 body 目标合同/工单归属，防止把交付挂到其他客户名下（与 create_delivery 一致）
    if scope is not None:
        if body.contract_id is not None:
            c = db.get(Contract, body.contract_id)
            if c is None or c.customer_id != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权将交付挂到其他客户合同")
        if body.work_order_id is not None:
            wo = db.get(WorkOrder, body.work_order_id)
            if wo is None or owning_customer_id(wo, db) != scope:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "无权将交付挂到其他客户工单")
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"delivery:{did}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(DeliveryOut.model_validate(obj).model_dump())


@router.delete("/{did}")
def delete_delivery(did: int, user: SysUser = Depends(require_role("sys_admin", "sys_ops")), db: Session = Depends(get_db)):
    obj = db.get(Delivery, did)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "交付不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"delivery:{did}")
    db.commit()
    return ok({"deleted": did})


@router.post("/{did}/sign")
def sign_delivery(did: int, user: SysUser = Depends(require_role(*SIGN_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Delivery, did)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "交付不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    obj.sign = "已签署"
    db.flush()
    record(db, user_id=user.id, action="sign", resource=f"delivery:{did}")
    db.commit()
    return ok(DeliveryOut.model_validate(obj).model_dump())
