"""驻场服务模型。"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OnsiteService(Base):
    """驻场配置：绑定客户/合同、人数、周期、工作项。"""

    __tablename__ = "onsite_service"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    headcount: Mapped[int] = mapped_column(Integer, default=1)  # 驻场人数
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_items: Mapped[str | None] = mapped_column(Text, nullable=True)  # 设备巡检/日志分析/漏洞打补丁/资产梳理/故障处置…
    status: Mapped[str] = mapped_column(String(16), default="执行中")  # 执行中/已结束
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OnsiteDailyReport(Base):
    """驻场日报：驻场人员逐日填报。"""

    __tablename__ = "onsite_daily_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    onsite_id: Mapped[int] = mapped_column(ForeignKey("onsite_service.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True)  # 驻场人员
    report_date: Mapped[date] = mapped_column(Date)
    work_type: Mapped[str] = mapped_column(String(32))  # 工作类型
    content: Mapped[str] = mapped_column(Text)  # 当日工作内容
    issue_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 逻辑引用 issue.id，异常转问题
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
