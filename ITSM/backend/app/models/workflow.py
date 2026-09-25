from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkflowRule(Base):
    """工作流规则：状态流转边，可覆盖/扩展内置默认状态机。"""

    __tablename__ = "workflow_rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(32), index=True)  # work_order/change_order/outsourcing
    from_status: Mapped[str] = mapped_column(String(32), index=True)
    to_status: Mapped[str] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 规则名/说明
    auto_action: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON：超时升级/提醒等自动化动作（后置）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ActionLog(Base):
    """动作日志：状态流转全量留痕（触发规则、时间、操作人）。"""

    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_rule.id"), nullable=True
    )
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("sys_user.id"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
