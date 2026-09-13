# -*- coding: utf-8 -*-
"""仪表盘布局模型"""

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class DashboardLayout(Base, UUIDMixin, TimestampMixin):
    """用户仪表盘布局"""
    __tablename__ = "dashboard_layouts"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    layout_name: Mapped[str] = mapped_column(String(128), default="default")
    widget_positions: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
