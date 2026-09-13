# -*- coding: utf-8 -*-
"""Agent 会话与任务模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class AgentSession(Base, UUIDMixin):
    """Agent 工作会话"""
    __tablename__ = "agent_sessions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sub_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")
    session_type: Mapped[str] = mapped_column(String(32), default="task", server_default="task")
    title: Mapped[str | None] = mapped_column(String(512))
    context_snapshot: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # ── 关联 ──
    agent = relationship("SubAgent", back_populates="sessions")
    project = relationship("Project", back_populates="agent_sessions")
    tasks = relationship("AgentTask", back_populates="session", cascade="all, delete-orphan")


class AgentTask(Base, UUIDMixin, TimestampMixin):
    """Agent 任务"""
    __tablename__ = "agent_tasks"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sub_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="SET NULL")
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id")
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    input_data: Mapped[dict | None] = mapped_column(JSONB)
    output_data: Mapped[dict | None] = mapped_column(JSONB)
    tool_calls: Mapped[list] = mapped_column(JSONB, default=list)
    progress: Mapped[float] = mapped_column(Float, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── 关联 ──
    agent = relationship("SubAgent", back_populates="tasks")
    session = relationship("AgentSession", back_populates="tasks")
    token_usages = relationship("AgentTokenUsage", back_populates="task", cascade="all, delete-orphan")


class AgentTokenUsage(Base, UUIDMixin):
    """Token 用量记录"""
    __tablename__ = "agent_token_usage"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sub_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="SET NULL")
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL")
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(64))
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # ── 关联 ──
    agent = relationship("SubAgent", back_populates="token_usages")
    task = relationship("AgentTask", back_populates="token_usages")
