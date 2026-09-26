"""签到打卡模型：GPS 定位签到 + 拍照留证。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CheckIn(Base):
    __tablename__ = "check_in"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True)
    check_type: Mapped[str] = mapped_column(String(8), default="签到")  # 签到 / 签退
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)  # 经度
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)  # 纬度
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 反地理编码文本
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 打卡照片
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
