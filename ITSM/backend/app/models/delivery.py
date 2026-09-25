"""项目交付模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Delivery(Base):
    __tablename__ = "delivery"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_order.id"), nullable=True, index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contract.id"), nullable=True, index=True)
    contract_item_id: Mapped[int | None] = mapped_column(ForeignKey("contract_item.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(128))
    report_type: Mapped[str] = mapped_column(String(32), default="运维报告")
    report_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 报告编号/文件引用
    sign: Mapped[str] = mapped_column(String(16), default="未签署")  # 未签署/已签署
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
