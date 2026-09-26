"""外包协作：外包人员名册 + 外包任务（状态机）+ 工作汇报。"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import (
    get_current_user,
    get_db,
    outsourcing_scope_of,
    require_role,
    role_rows_of,
)
from app.models import Outsourcing, OutsourcingReport, OutsourceUser, SysUser
from app.schemas.outsourcing import (
    OutsourcingCreate,
    OutsourcingOut,
    OutsourcingReportCreate,
    OutsourcingReportOut,
    OutsourcingReportUpdate,
    OutsourcingStatusUpdate,
    OutsourcingUpdate,
    OutsourceUserCreate,
    OutsourceUserOut,
    OutsourceUserUpdate,
)
from app.services.audit_service import record
from app.services.outsourcing_service import transition_status
from app.utils.pagination import paginate
from app.utils.response import ok

RW_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")
DEL_ROLE = ("sys_admin", "sys_ops")
OUTSOURCE_ROLE = "outsource"


def _scope_of(user: SysUser, db: Session) -> int | None:
    """外包任务可见范围：平台角色→None(全部)；外包人员→其 outsource_user_id；否则 403。"""
    roles = {r.code for r in role_rows_of(user, db)}
    if roles & set(RW_ROLE):
        return None
    if OUTSOURCE_ROLE in roles:
        sid = outsourcing_scope_of(user, db)
        if sid is not None:
            return sid
    raise HTTPException(status.HTTP_403_FORBIDDEN, "权限不足")

users = APIRouter(prefix="/outsource-users", tags=["外包人员"])
outsourcings = APIRouter(prefix="/outsourcings", tags=["外包任务"])
reports = APIRouter(prefix="/outsourcing-reports", tags=["外包汇报"])


# ---- 外包人员 ----
@users.get("")
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*RW_ROLE)),
    db: Session = Depends(get_db),
):
    return ok(paginate(db.query(OutsourceUser), page, size, OutsourceUserOut))


@users.post("")
def create_user(body: OutsourceUserCreate, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = OutsourceUser(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"outsource_user:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(OutsourceUserOut.model_validate(obj).model_dump())


@users.get("/{uid}")
def get_user(uid: int, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(OutsourceUser, uid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包人员不存在")
    return ok(OutsourceUserOut.model_validate(obj).model_dump())


@users.put("/{uid}")
def update_user(uid: int, body: OutsourceUserUpdate, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(OutsourceUser, uid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包人员不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"outsource_user:{uid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(OutsourceUserOut.model_validate(obj).model_dump())


@users.delete("/{uid}")
def delete_user(uid: int, user: SysUser = Depends(require_role(*DEL_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(OutsourceUser, uid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包人员不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"outsource_user:{uid}")
    db.commit()
    return ok({"deleted": uid})


# ---- 外包任务 ----
@outsourcings.get("")
def list_outsourcings(
    work_order_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = _scope_of(user, db)
    q = db.query(Outsourcing)
    if scope is not None:
        q = q.filter(Outsourcing.outsource_user_id == scope)  # 外包仅见自己
    if work_order_id is not None:
        q = q.filter(Outsourcing.work_order_id == work_order_id)
    return ok(paginate(q, page, size, OutsourcingOut))


@outsourcings.post("")
def create_outsourcing(body: OutsourcingCreate, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = Outsourcing(**body.model_dump())
    db.add(obj)
    db.flush()
    after = body.model_dump()
    if after.get("nda") is not None:
        after["nda"] = "***"  # 保密协议字段级加密，审计不留明文
    record(db, user_id=user.id, action="create", resource=f"outsourcing:{obj.id}", after=str(after))
    db.commit()
    return ok(OutsourcingOut.model_validate(obj).model_dump())


@outsourcings.get("/{oid}")
def get_outsourcing(oid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    scope = _scope_of(user, db)
    obj = db.get(Outsourcing, oid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包任务不存在")
    if scope is not None and obj.outsource_user_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问他人外包任务")
    return ok(OutsourcingOut.model_validate(obj).model_dump())


@outsourcings.put("/{oid}")
def update_outsourcing(oid: int, body: OutsourcingUpdate, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Outsourcing, oid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包任务不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    after = body.model_dump(exclude_unset=True)
    if after.get("nda") is not None:
        after["nda"] = "***"  # 保密协议字段级加密，审计不留明文
    record(db, user_id=user.id, action="update", resource=f"outsourcing:{oid}", after=str(after))
    db.commit()
    return ok(OutsourcingOut.model_validate(obj).model_dump())


@outsourcings.put("/{oid}/status")
def update_outsourcing_status(oid: int, body: OutsourcingStatusUpdate, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Outsourcing, oid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包任务不存在")
    try:
        transition_status(db, obj, body.status, operator_id=user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="update_status", resource=f"outsourcing:{oid}", after=body.status)
    db.commit()
    return ok(OutsourcingOut.model_validate(obj).model_dump())


@outsourcings.delete("/{oid}")
def delete_outsourcing(oid: int, user: SysUser = Depends(require_role(*DEL_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(Outsourcing, oid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包任务不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"outsourcing:{oid}")
    db.commit()
    return ok({"deleted": oid})


@outsourcings.post("/{oid}/accept")
def accept_outsourcing(oid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """外包接单（待接单 → 已接单），仅限被指派的外包人员本人。"""
    scope = _scope_of(user, db)
    obj = db.get(Outsourcing, oid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包任务不存在")
    if scope is None or obj.outsource_user_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅被指派的外包人员可接单")
    try:
        transition_status(db, obj, "已接单", operator_id=user.id, note="外包接单")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="accept", resource=f"outsourcing:{oid}", after="已接单")
    db.commit()
    return ok(OutsourcingOut.model_validate(obj).model_dump())


@outsourcings.post("/{oid}/reject")
def reject_outsourcing(oid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """外包拒单（待接单 → 已拒单），仅限被指派的外包人员本人。"""
    scope = _scope_of(user, db)
    obj = db.get(Outsourcing, oid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包任务不存在")
    if scope is None or obj.outsource_user_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅被指派的外包人员可拒单")
    try:
        transition_status(db, obj, "已拒单", operator_id=user.id, note="外包拒单")
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    record(db, user_id=user.id, action="reject", resource=f"outsourcing:{oid}", after="已拒单")
    db.commit()
    return ok(OutsourcingOut.model_validate(obj).model_dump())


# ---- 外包汇报 ----
@reports.get("")
def list_reports(
    outsourcing_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = _scope_of(user, db)
    q = db.query(OutsourcingReport)
    if scope is not None:
        q = q.join(Outsourcing, OutsourcingReport.outsourcing_id == Outsourcing.id).filter(
            Outsourcing.outsource_user_id == scope
        )
    if outsourcing_id is not None:
        q = q.filter(OutsourcingReport.outsourcing_id == outsourcing_id)
    return ok(paginate(q, page, size, OutsourcingReportOut))


@reports.post("")
def create_report(body: OutsourcingReportCreate, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    scope = _scope_of(user, db)
    if scope is not None:
        o = db.get(Outsourcing, body.outsourcing_id)
        if o is None or o.outsource_user_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "仅能为自己的外包任务提交汇报")
    obj = OutsourcingReport(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"outsourcing_report:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(OutsourcingReportOut.model_validate(obj).model_dump())


@reports.get("/{rid}")
def get_report(rid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    scope = _scope_of(user, db)
    obj = db.get(OutsourcingReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包汇报不存在")
    if scope is not None:
        o = db.get(Outsourcing, obj.outsourcing_id)
        if o is None or o.outsource_user_id != scope:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问他人外包汇报")
    return ok(OutsourcingReportOut.model_validate(obj).model_dump())


@reports.put("/{rid}")
def update_report(rid: int, body: OutsourcingReportUpdate, user: SysUser = Depends(require_role(*RW_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(OutsourcingReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包汇报不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"outsourcing_report:{rid}", after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(OutsourcingReportOut.model_validate(obj).model_dump())


@reports.delete("/{rid}")
def delete_report(rid: int, user: SysUser = Depends(require_role(*DEL_ROLE)), db: Session = Depends(get_db)):
    obj = db.get(OutsourcingReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "外包汇报不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"outsourcing_report:{rid}")
    db.commit()
    return ok({"deleted": rid})
