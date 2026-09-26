"""审批流模型：状态流转的审批关卡。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Approval(Base):
    __tablename__ = "approval"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(32))  # work_order / change_order / outsourcing
    entity_id: Mapped[int] = mapped_column(Integer)
    from_status: Mapped[str] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    applicant_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), index=True)  # 申请人
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)  # 审批人
    status: Mapped[str] = mapped_column(String(16), default="待审批")  # 待审批/已通过/已拒绝
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 申请理由
    decision_note: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 审批意见
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
