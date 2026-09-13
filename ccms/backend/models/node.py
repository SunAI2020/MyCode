# -*- coding: utf-8 -*-
"""计算节点模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class Node(Base, UUIDMixin, TimestampMixin):
    """计算节点 — 运行 CCMS 后端的物理机/虚拟机/容器实例"""
    __tablename__ = "nodes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), default="local", server_default="local")
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="offline", server_default="offline", index=True)
    capabilities: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
