from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderReceive(Base):
    __tablename__ = "order_receive"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="客户报障")  # 客户报障/商务拓展/巡检发现/安全事件/续约/临时新增
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contract.id"), nullable=True)
    contract_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("contract_item.id"), nullable=True
    )
    ci_id: Mapped[int | None] = mapped_column(ForeignKey("cmdb_ci.id"), nullable=True)
    project: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_price: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 甲方联系人/电话（脱敏）
    service_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    accept_standard: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkOrder(Base):
    __tablename__ = "work_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    no: Mapped[str] = mapped_column(String(32), unique=True)  # WO-YYYY-NNNN
    type: Mapped[str] = mapped_column(String(16), default="客户工单")  # 客户工单/驻场工单/内部任务/外包工单
    receive_id: Mapped[int | None] = mapped_column(ForeignKey("order_receive.id"), nullable=True)
    # dispatch_id 用逻辑引用（避免与 order_dispatch.work_order_id 形成循环外键）
    dispatch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contract.id"), nullable=True)
    contract_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("contract_item.id"), nullable=True
    )
    ci_id: Mapped[int | None] = mapped_column(ForeignKey("cmdb_ci.id"), nullable=True)
    project: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 报障/需求描述
    task_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 内部任务类型：内部研发/制度建设/报告编写/培训准备/其他
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 内部任务截止时间
    status: Mapped[str] = mapped_column(String(16), default="待派单")  # 待派单/已派单/计划中/进行中/待验收/已完成/已关闭/已取消
    priority: Mapped[str] = mapped_column(String(8), default="中")  # 高/中/低
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    current_cycle_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkOrderAssignee(Base):
    __tablename__ = "work_order_assignee"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_order.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"))
    workload_ratio: Mapped[float] = mapped_column(Numeric(5, 2), default=100)  # 工作量比例 %
    actual_hours: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
