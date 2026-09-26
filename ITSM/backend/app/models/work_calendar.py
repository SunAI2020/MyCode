"""工作日历模型：SLA 计时跳过非工作时段。"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkCalendar(Base):
    __tablename__ = "work_calendar"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    work_days: Mapped[str] = mapped_column(String(32), default="1,2,3,4,5")  # ISO weekday 1=周一
    work_start: Mapped[str] = mapped_column(String(5), default="09:00")  # HH:MM
    work_end: Mapped[str] = mapped_column(String(5), default="18:00")
    holidays: Mapped[str | None] = mapped_column(Text, nullable=True)  # 节假日日期逗号分隔
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
