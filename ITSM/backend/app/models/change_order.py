"""变更单模型。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChangeOrder(Base):
    """变更单：挂接 CI，风险评估 + 冲突检测 + 回滚计划。"""

    __tablename__ = "change_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int | None] = mapped_column(ForeignKey("work_order.id"), nullable=True, index=True)
    ci_id: Mapped[int] = mapped_column(ForeignKey("cmdb_ci.id"), index=True)  # 关联配置项
    risk_level: Mapped[str] = mapped_column(String(8), default="中")  # 高/中/低
    conflict_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # 同 CI 活跃变更冲突
    rollback_plan: Mapped[str | None] = mapped_column(Text, nullable=True)  # 回滚计划
    status: Mapped[str] = mapped_column(String(16), default="草稿")  # 草稿/待审批/已批准/实施中/已完成/已回滚/已拒绝/已取消
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
