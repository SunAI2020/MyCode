"""绩效考核模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Performance(Base):
    __tablename__ = "performance"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_order.id"), index=True)
    contract_item_id: Mapped[int | None] = mapped_column(ForeignKey("contract_item.id"), nullable=True)
    workload: Mapped[float] = mapped_column(Numeric(10, 2), default=0)  # 工作量(工时)
    dispatch_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    ratio: Mapped[float] = mapped_column(Numeric(5, 2), default=100)  # 分摊比例 %
    quality_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)  # 0.6~1.2
    customer_score: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0)  # 0.8~1.2
    perf_score: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
