"""驻场服务 + 驻场日报 CRUD + 周/月报聚合。"""
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
from app.models import Contract, OnsiteAssignment, OnsiteDailyReport, OnsiteService, SysUser
from app.schemas.onsite import (
    OnsiteAssignmentCreate,
    OnsiteAssignmentOut,
    OnsiteAssignmentUpdate,
    OnsiteDailyReportCreate,
    OnsiteDailyReportOut,
    OnsiteDailyReportUpdate,
    OnsiteServiceCreate,
    OnsiteServiceOut,
    OnsiteServiceUpdate,
)
from app.services.audit_service import record
from app.services.onsite_service import summarize_reports
from app.utils.pagination import paginate
from app.utils.response import ok

WRITE_ROLE = ("sys_admin", "sys_ops", "ticket_mgr")

services = APIRouter(prefix="/onsite-services", tags=["驻场服务"])
reports = APIRouter(prefix="/onsite-daily-reports", tags=["驻场日报"])
assignments = APIRouter(prefix="/onsite-assignments", tags=["驻场人员"])


def _assert_report_scoped(obj: OnsiteDailyReport, scope: int | None, db: Session) -> None:
    """日报行级隔离：经 onsite_service.customer_id 校验。"""
    if scope is None:
        return
    os = db.get(OnsiteService, obj.onsite_id)
    if os is None or os.customer_id != scope:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "资源不存在或无权访问")


# ---- 驻场配置 ----
@services.get("")
def list_services(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = scope_filter(db.query(OnsiteService), OnsiteService, scope)
    return ok(paginate(q, page, size, OnsiteServiceOut))


@services.post("")
def create_service(
    body: OnsiteServiceCreate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    if scope is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权为其他客户创建驻场配置")
    c = db.get(Contract, body.contract_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
    if c.customer_id != body.customer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "合同与客户不匹配")
    obj = OnsiteService(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"onsite_service:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(OnsiteServiceOut.model_validate(obj).model_dump())


@services.get("/{sid}")
def get_service(sid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(OnsiteService, sid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    assert_scoped(obj, customer_scope_of(user, db), db)
    return ok(OnsiteServiceOut.model_validate(obj).model_dump())


@services.put("/{sid}")
def update_service(
    sid: int,
    body: OnsiteServiceUpdate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(OnsiteService, sid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    scope = customer_scope_of(user, db)
    assert_scoped(obj, scope, db)
    if scope is not None and body.customer_id is not None and body.customer_id != scope:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权将驻场配置挂到其他客户")
    if body.contract_id is not None:
        c = db.get(Contract, body.contract_id)
        if c is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        target_cid = body.customer_id if body.customer_id is not None else obj.customer_id
        if c.customer_id != target_cid:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "合同与客户不匹配")
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"onsite_service:{sid}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(OnsiteServiceOut.model_validate(obj).model_dump())


@services.delete("/{sid}")
def delete_service(sid: int, user: SysUser = Depends(require_role("sys_admin", "sys_ops")), db: Session = Depends(get_db)):
    obj = db.get(OnsiteService, sid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"onsite_service:{sid}")
    db.commit()
    return ok({"deleted": sid})


# ---- 驻场日报 ----
@reports.get("")
def list_reports(
    onsite_id: int | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scope = customer_scope_of(user, db)
    q = db.query(OnsiteDailyReport)
    if scope is not None:
        q = q.join(OnsiteService, OnsiteDailyReport.onsite_id == OnsiteService.id).filter(OnsiteService.customer_id == scope)
    if onsite_id is not None:
        q = q.filter(OnsiteDailyReport.onsite_id == onsite_id)
    if start is not None:
        q = q.filter(OnsiteDailyReport.report_date >= start)
    if end is not None:
        q = q.filter(OnsiteDailyReport.report_date <= end)
    return ok(paginate(q, page, size, OnsiteDailyReportOut))


@reports.post("")
def create_report(
    body: OnsiteDailyReportCreate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    os = db.get(OnsiteService, body.onsite_id)
    if os is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    assert_scoped(os, customer_scope_of(user, db), db)
    obj = OnsiteDailyReport(**body.model_dump(), user_id=user.id)  # 作者取当前用户，防冒名
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"onsite_daily_report:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(OnsiteDailyReportOut.model_validate(obj).model_dump())


@reports.get("/summary")
def report_summary(
    onsite_id: int = Query(...),
    start: date | None = Query(None),
    end: date | None = Query(None),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    os = db.get(OnsiteService, onsite_id)
    if os is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    assert_scoped(os, customer_scope_of(user, db), db)
    return ok(summarize_reports(db, onsite_id, start, end))


@reports.get("/{rid}")
def get_report(rid: int, user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(OnsiteDailyReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "日报不存在")
    _assert_report_scoped(obj, customer_scope_of(user, db), db)
    return ok(OnsiteDailyReportOut.model_validate(obj).model_dump())


@reports.put("/{rid}")
def update_report(
    rid: int,
    body: OnsiteDailyReportUpdate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(OnsiteDailyReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "日报不存在")
    _assert_report_scoped(obj, customer_scope_of(user, db), db)
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"onsite_daily_report:{rid}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(OnsiteDailyReportOut.model_validate(obj).model_dump())


@reports.delete("/{rid}")
def delete_report(rid: int, user: SysUser = Depends(require_role("sys_admin", "sys_ops")), db: Session = Depends(get_db)):
    obj = db.get(OnsiteDailyReport, rid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "日报不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"onsite_daily_report:{rid}")
    db.commit()
    return ok({"deleted": rid})


# ---- 驻场人员清单 ----
@assignments.get("")
def list_assignments(
    onsite_id: int = Query(...),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    os = db.get(OnsiteService, onsite_id)
    if os is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    assert_scoped(os, customer_scope_of(user, db), db)
    rows = db.query(OnsiteAssignment).filter_by(onsite_id=onsite_id).order_by(OnsiteAssignment.id).all()
    return ok([OnsiteAssignmentOut.model_validate(a).model_dump() for a in rows])


@assignments.post("")
def create_assignment(
    body: OnsiteAssignmentCreate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    os = db.get(OnsiteService, body.onsite_id)
    if os is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场配置不存在")
    assert_scoped(os, customer_scope_of(user, db), db)
    obj = OnsiteAssignment(**body.model_dump())
    db.add(obj)
    db.flush()
    record(db, user_id=user.id, action="create", resource=f"onsite_assignment:{obj.id}", after=str(body.model_dump()))
    db.commit()
    return ok(OnsiteAssignmentOut.model_validate(obj).model_dump())


@assignments.put("/{aid}")
def update_assignment(
    aid: int,
    body: OnsiteAssignmentUpdate,
    user: SysUser = Depends(require_role(*WRITE_ROLE)),
    db: Session = Depends(get_db),
):
    obj = db.get(OnsiteAssignment, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场人员不存在")
    os = db.get(OnsiteService, obj.onsite_id)
    assert_scoped(os, customer_scope_of(user, db), db)
    before = {k: getattr(obj, k) for k in body.model_dump(exclude_unset=True)}
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)  # 换岗：status 改离岗 / end_date
    db.flush()
    record(db, user_id=user.id, action="update", resource=f"onsite_assignment:{aid}", before=str(before), after=str(body.model_dump(exclude_unset=True)))
    db.commit()
    return ok(OnsiteAssignmentOut.model_validate(obj).model_dump())


@assignments.delete("/{aid}")
def delete_assignment(aid: int, user: SysUser = Depends(require_role("sys_admin", "sys_ops")), db: Session = Depends(get_db)):
    obj = db.get(OnsiteAssignment, aid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "驻场人员不存在")
    db.delete(obj)
    record(db, user_id=user.id, action="delete", resource=f"onsite_assignment:{aid}")
    db.commit()
    return ok({"deleted": aid})
