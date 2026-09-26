"""签到打卡单测：创建 + 每日去重 + 今日状态。"""
import pytest
from fastapi import HTTPException

from app.api.v1.checkins import create_checkin, today
from app.models import CheckIn, SysUser
from app.schemas.checkin import CheckInCreate


def _user(db):
    u = SysUser(username="staff", name="安服", pwd_hash="x")
    db.add(u)
    db.commit()
    return u


def test_create_checkin(db):
    u = _user(db)
    data = create_checkin(
        CheckInCreate(check_type="签到", longitude=116.4, latitude=39.9), user=u, db=db
    )["data"]
    assert data["user_id"] == u.id
    assert data["check_type"] == "签到"
    assert float(data["longitude"]) == 116.4
    assert float(data["latitude"]) == 39.9


def test_duplicate_same_type_rejected(db):
    u = _user(db)
    create_checkin(CheckInCreate(check_type="签到"), user=u, db=db)
    with pytest.raises(HTTPException) as exc:
        create_checkin(CheckInCreate(check_type="签到"), user=u, db=db)
    assert exc.value.status_code == 400


def test_sign_in_then_out_allowed(db):
    u = _user(db)
    create_checkin(CheckInCreate(check_type="签到"), user=u, db=db)
    create_checkin(CheckInCreate(check_type="签退"), user=u, db=db)  # 不同类型不冲突
    assert db.query(CheckIn).filter_by(user_id=u.id).count() == 2


def test_today(db):
    u = _user(db)
    create_checkin(CheckInCreate(check_type="签到"), user=u, db=db)
    data = today(user=u, db=db)["data"]
    assert len(data["records"]) == 1
    assert data["records"][0]["check_type"] == "签到"
