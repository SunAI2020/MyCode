"""签到打卡：GPS 定位签到 + 拍照留证（移动端服务人员）。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models import CheckIn, SysUser
from app.schemas.checkin import CheckInCreate, CheckInOut
from app.utils.pagination import paginate
from app.utils.response import ok

router = APIRouter(prefix="/checkins", tags=["签到打卡"])


def _local_today_bounds() -> tuple[datetime, datetime]:
    """本地「今日」的 [00:00, 次日 00:00) 区间，转成 UTC 且去时区。

    created_at 由 server_default=func.now() 生成（SQLite/Postgres 均为 UTC），而
    date.today() 是本地时间；直接用 func.date(created_at) 比对，会在东八区 00:00~08:00
    跨天后相差一天。故改用「本地日区间 → UTC」的范围比较。
    """
    now = datetime.now().astimezone()  # 本地时区感知
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


@router.post("")
def create_checkin(
    body: CheckInCreate,
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """签到/签退（GPS + 照片）。同类型每日一次，重复返回 400。"""
    start, end = _local_today_bounds()
    dup = (
        db.query(CheckIn)
        .filter(
            CheckIn.user_id == user.id,
            CheckIn.check_type == body.check_type,
            CheckIn.created_at >= start,
            CheckIn.created_at < end,
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
    start, end = _local_today_bounds()
    rows = (
        db.query(CheckIn)
        .filter(
            CheckIn.user_id == user.id,
            CheckIn.created_at >= start,
            CheckIn.created_at < end,
        )
        .order_by(CheckIn.id.asc())
        .all()
    )
    return ok({"records": [CheckInOut.model_validate(r).model_dump() for r in rows]})
