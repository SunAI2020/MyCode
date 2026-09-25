from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SlaPolicy(Base):
    __tablename__ = "sla_policy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    customer_level: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 金牌/银牌/普通
    response_limit: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 响应时限
    resolve_limit: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 解决时限
    work_calendar_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_chain: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 升级链


class ServiceCycle(Base):
    __tablename__ = "service_cycle"
    __table_args__ = (
        UniqueConstraint("contract_item_id", "cycle_no", name="uq_cycle_item_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_item_id: Mapped[int] = mapped_column(
        ForeignKey("contract_item.id"), index=True
    )
    cycle_no: Mapped[int] = mapped_column(Integer)
    service_start: Mapped[date] = mapped_column(Date)
    service_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/started/done
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ServiceReminder(Base):
    __tablename__ = "service_reminder"

    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_cycle.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(16), default="启动")  # 启动/预警
    level: Mapped[str] = mapped_column(String(8), default="黄")  # 黄/橙/红
    content: Mapped[str] = mapped_column(String(255))
    to_user_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 站内/短信/企微/飞书/钉钉
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
