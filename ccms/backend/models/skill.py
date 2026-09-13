# -*- coding: utf-8 -*-
"""技能模型"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Skill(Base, UUIDMixin, TimestampMixin):
    """技能定义"""
    __tablename__ = "skills"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    skill_type: Mapped[str] = mapped_column(String(64), default="tool", server_default="tool")
    definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    version: Mapped[str] = mapped_column(String(16), default="1.0.0", server_default="1.0.0")

    agents = relationship("AgentSkill", back_populates="skill", cascade="all, delete-orphan")
