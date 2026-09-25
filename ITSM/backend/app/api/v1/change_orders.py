"""变更单 CRUD + 状态流转 + 冲突检测。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.models import ChangeOrder, SysUser
from app.schemas.change_order import (
    ChangeOrderCreate,
    ChangeOrderOut,
    ChangeOrderStatusUpdate,
    ChangeOrderUpdate,
)
from app.services.audit_service import record
from app.services.change_service import set_conflict_flag, transition_status
from app.utils.pagination import paginate
from app.utils.response import ok

RW_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")
DEL_ROLE = ("sys_admin", "sys_ops")

router = APIRouter(prefix="/change-orders", tags=["变更单"])


@router.get("")
def list_change_orders(
    ci_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(ChangeOrder)
    if ci_id is not None:
        q = q.filter(ChangeOrder.ci_id == ci_id)
    return ok(paginate(q, page, size, ChangeOrderOut))


@router.post("")
def create_change_order(
    body: ChangeOrderCreate,
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    obj = ChangeOrder(**body.model_dump())
    db.add(obj)
    db.flush()
    set_conflict_flag(db, obj)
    record(db, user_id=user.id, action="create", resource=f"change_order:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(ChangeOrderOut.model_validate(obj).model_dump())


@router.get("/{cid}")
def get_change_order(cid: int, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(ChangeOrder, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更单不存在")
    return ok(ChangeOrderOut.model_validate(obj).model_dump())


@router.put("/{cid}")
def update_change_order(
    cid: int,
    body: ChangeOrderUpdate,
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(ChangeOrder, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更单不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    set_conflict_flag(db, obj)
    record(db, user_id=user.id, action="update", resource=f"change_order:{cid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(ChangeOrderOut.model_validate(obj).model_dump())


@router.put("/{cid}/status")
def update_change_order_status(
    cid: int,
    body: ChangeOrderStatusUpdate,
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(ChangeOrder, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更单不存在")
    try:
        transition_status(db, obj, body.status, operator_id=user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    set_conflict_flag(db, obj)
    record(db, user_id=user.id, action="update_status", resource=f"change_order:{cid}", after=body.status)
    db.commit()
    return ok(ChangeOrderOut.model_validate(obj).model_dump())


@router.delete("/{cid}")
def delete_change_order(cid: int, user: SysUser = Depends(require_role(*DEL_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(ChangeOrder, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "变更单不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"change_order:{cid}")
    db.commit()
    return ok({"deleted": cid})
