# -*- coding: utf-8 -*-
"""终端会话模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin


class TerminalSession(Base, UUIDMixin):
    """终端会话记录"""
    __tablename__ = "terminal_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    session_name: Mapped[str | None] = mapped_column(String(255))
    working_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    shell_type: Mapped[str] = mapped_column(String(64), default="bash", server_default="bash")
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active", index=True)
    pid: Mapped[int | None] = mapped_column(Integer)
    output_buffer: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
