"""问题整改闭环模型：issue / rectification / rectification_record。"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Issue(Base):
    __tablename__ = "issue"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_order.id"), index=True)
    requirement_id: Mapped[int | None] = mapped_column(
        ForeignKey("compliance_requirement.id"), nullable=True, index=True
    )  # 合规要求挂接（步骤 51：合规缺口→问题→整改→核验 闭环）
    type: Mapped[str] = mapped_column(String(32), default="安全漏洞")  # 安全漏洞/配置缺陷/基线不合规/风险隐患
    level: Mapped[str] = mapped_column(String(8), default="中危")  # 严重/高危/中危/低危/信息（CVE/CVSS）
    description: Mapped[str] = mapped_column(Text)
    attachments: Mapped[str | None] = mapped_column(Text, nullable=True)
    similar_ids: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="待整改")  # 待整改/整改中/已关闭
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Rectification(Base):
    __tablename__ = "rectification"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id"), index=True)
    plan: Mapped[str] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee: Mapped[int | None] = mapped_column(Integer, nullable=True)  # user_id 逻辑引用
    status: Mapped[str] = mapped_column(String(16), default="整改中")  # 整改中/已通过/已关闭
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RectificationRecord(Base):
    __tablename__ = "rectification_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    rectification_id: Mapped[int] = mapped_column(ForeignKey("rectification.id"), index=True)
    round_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)  # 本轮整改动作/内容
    executor: Mapped[int | None] = mapped_column(Integer, nullable=True)  # user_id 逻辑引用
    effect: Mapped[str] = mapped_column(String(16))  # 通过/不通过/部分完成
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
