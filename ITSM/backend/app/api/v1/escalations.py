"""SLA 升级记录查询。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.models import Escalation, SysUser
from app.schemas.escalation import EscalationOut
from app.utils.pagination import paginate
from app.utils.response import ok

router = APIRouter(prefix="/escalations", tags=["SLA升级"])

ROLE = ("sys_admin", "sys_ops", "ticket_mgr")


@router.get("")
def list_escalations(
    work_order_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(require_role(*ROLE)),
    db: Session = Depends(get_db),
):
    q = db.query(Escalation).order_by(Escalation.id.desc())
    if work_order_id is not None:
        q = q.filter(Escalation.work_order_id == work_order_id)
    return ok(paginate(q, page, size, EscalationOut))
