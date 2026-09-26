"""外包协作模型。"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.crypto import EncryptedText
from app.db.base import Base


class OutsourceUser(Base):
    """外包人员名册（平台内部）。"""

    __tablename__ = "outsource_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    org: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 单位
    qualification: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 资质
    settle_type: Mapped[str] = mapped_column(String(16), default="按次")  # 按次/按月/按工时
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)  # 权限范围
    user_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)  # 绑定登录账号（外包人员）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Outsourcing(Base):
    """外包任务：内部工单发起外包。"""

    __tablename__ = "outsourcing"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_order.id"), index=True)
    type: Mapped[str] = mapped_column(String(16), default="能力")  # 能力/时间/资质
    outsource_user_id: Mapped[int] = mapped_column(ForeignKey("outsource_user.id"), index=True)
    price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    nda: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # 保密协议（字段级加密落库）
    status: Mapped[str] = mapped_column(String(16), default="待接单")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OutsourcingReport(Base):
    """外包工作汇报/验收。"""

    __tablename__ = "outsourcing_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    outsourcing_id: Mapped[int] = mapped_column(ForeignKey("outsourcing.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date)
    progress: Mapped[str | None] = mapped_column(Text, nullable=True)  # 工作进展
    attachments: Mapped[str | None] = mapped_column(Text, nullable=True)  # 附件
    acceptance: Mapped[str | None] = mapped_column(Text, nullable=True)  # 验收结论
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
