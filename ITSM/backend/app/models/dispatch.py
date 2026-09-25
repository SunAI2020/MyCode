from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderDispatch(Base):
    __tablename__ = "order_dispatch"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_order.id"), index=True)
    dispatch_type: Mapped[str] = mapped_column(String(16), default="内部")  # 内部/外包
    dispatch_price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    service_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    accept_standard: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggest_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # AI 派单建议理由
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
