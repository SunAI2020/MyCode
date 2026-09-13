# -*- coding: utf-8 -*-
"""用户设置模型"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class Setting(Base, UUIDMixin, TimestampMixin):
    """用户设置 (key-value)"""
    __tablename__ = "settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    setting_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    setting_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    setting_group: Mapped[str] = mapped_column(String(64), default="general")
