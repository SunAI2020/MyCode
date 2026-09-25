"""知识库模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KbArticle(Base):
    """知识条目：漏洞/整改方案/故障手册/SOP/驻场规范。"""

    __tablename__ = "kb_article"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32), default="故障手册")  # 漏洞/整改方案/故障手册/SOP/驻场规范/其他
    content: Mapped[str] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 逗号分隔
    status: Mapped[str] = mapped_column(String(16), default="已发布")  # 草稿/已发布
    author_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
