"""签到打卡 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CheckInCreate(BaseModel):
    check_type: str = "签到"  # 签到 / 签退
    longitude: float | None = None
    latitude: float | None = None
    address: str | None = None
    photo_url: str | None = None
    remark: str | None = None


class CheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    check_type: str
    longitude: float | None = None
    latitude: float | None = None
    address: str | None = None
    photo_url: str | None = None
    remark: str | None = None
    created_at: datetime | None = None
