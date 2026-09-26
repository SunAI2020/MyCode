"""工作日历 CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import customer_scope_of, get_db, require_role
from app.models import SysUser, WorkCalendar
from app.schemas.work_calendar import WorkCalendarCreate, WorkCalendarOut
from app.utils.response import ok

router = APIRouter(prefix="/work-calendars", tags=["工作日历"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")


def _deny_scoped(user: SysUser, db: Session) -> None:
    """工作日历为全局配置，拒绝带客户 scope 的用户。"""
    if customer_scope_of(user, db) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问全局工作日历")


@router.get("")
def list_calendars(user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    _deny_scoped(user, db)
    rows = db.query(WorkCalendar).order_by(WorkCalendar.id).all()
    return ok([WorkCalendarOut.model_validate(r).model_dump() for r in rows])


@router.post("")
def create_calendar(body: WorkCalendarCreate, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    _deny_scoped(user, db)
    obj = WorkCalendar(**body.model_dump())
    db.add(obj)
    db.commit()
    return ok(WorkCalendarOut.model_validate(obj).model_dump())


@router.delete("/{cid}")
def delete_calendar(cid: int, user: SysUser = Depends(require_role(*ROLE)), db: Session = Depends(get_db)):
    _deny_scoped(user, db)
    obj = db.get(WorkCalendar, cid)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "工作日历不存在")
    db.delete(obj)
    db.commit()
    return ok({"deleted": cid})
