"""SLA 升级记录模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Escalation(Base):
    __tablename__ = "escalation"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("work_order.id"), nullable=True, index=True
    )
    level: Mapped[str] = mapped_column(String(8))  # 红/橙/黄
    from_user: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 升级链节点名
    to_user: Mapped[str | None] = mapped_column(String(64), nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
