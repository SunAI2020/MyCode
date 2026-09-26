"""签到打卡：GPS 定位签到 + 拍照留证（移动端服务人员）。"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import CheckIn, SysUser
from app.schemas.checkin import CheckInCreate, CheckInOut
from app.utils.pagination import paginate
from app.utils.response import ok

router = APIRouter(prefix="/checkins", tags=["签到打卡"])


@router.post("")
def create_checkin(
    body: CheckInCreate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """签到/签退（GPS + 照片）。同类型每日一次，重复返回 400。"""
    today = date.today()
    dup = (
        db.query(CheckIn)
        .filter(
            CheckIn.user_id == user.id,
            CheckIn.check_type == body.check_type,
            func.date(CheckIn.created_at) == today,
        )
        .first()
    )
    if dup:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"今日已{body.check_type}")
    obj = CheckIn(user_id=user.id, **body.model_dump())
    db.add(obj)
    db.commit()
    return ok(CheckInOut.model_validate(obj).model_dump())


@router.get("")
def list_checkins(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的签到记录（倒序分页）。"""
    q = db.query(CheckIn).filter(CheckIn.user_id == user.id).order_by(CheckIn.id.desc())
    return ok(paginate(q, page, size, CheckInOut))


@router.get("/today")
def today(user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """今日签到状态：返回今日全部打卡记录，移动端据此判断是否已签到/签退。"""
    rows = (
        db.query(CheckIn)
        .filter(
            CheckIn.user_id == user.id,
            func.date(CheckIn.created_at) == date.today(),
        )
        .order_by(CheckIn.id.asc())
        .all()
    )
    return ok({"records": [CheckInOut.model_validate(r).model_dump() for r in rows]})
