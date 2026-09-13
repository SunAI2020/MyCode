# -*- coding: utf-8 -*-
"""子 Agent 模型"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class AgentRolePreset(Base, UUIDMixin, TimestampMixin):
    """Agent 角色预设"""
    __tablename__ = "agent_role_presets"

    role_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    default_model: Mapped[str] = mapped_column(String(64), default="claude-sonnet-4-20250514")
    default_max_tokens: Mapped[int] = mapped_column(Integer, default=8192)
    default_temperature: Mapped[float] = mapped_column(Float, default=0.7)
    icon_name: Mapped[str | None] = mapped_column(String(64))
    sprite_sheet: Mapped[str | None] = mapped_column(String(255))
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # ── 关联 ──
    agents = relationship("SubAgent", back_populates="role_preset")


class SubAgent(Base, UUIDMixin, TimestampMixin):
    """子 Agent 实例"""
    __tablename__ = "sub_agents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    role_preset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_role_presets.id")
    )
    custom_role_name: Mapped[str | None] = mapped_column(String(128))
    custom_system_prompt: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="idle", server_default="idle", index=True
    )
    model: Mapped[str] = mapped_column(String(64), default="claude-sonnet-4-20250514")
    max_tokens: Mapped[int] = mapped_column(Integer, default=8192)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    max_concurrent_tasks: Mapped[int] = mapped_column(Integer, default=3)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── 关联 ──
    owner = relationship("User", back_populates="sub_agents")
    role_preset = relationship("AgentRolePreset", back_populates="agents")
    skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")
    sessions = relationship("AgentSession", back_populates="agent", cascade="all, delete-orphan")
    tasks = relationship("AgentTask", back_populates="agent", cascade="all, delete-orphan")
    token_usages = relationship("AgentTokenUsage", back_populates="agent", cascade="all, delete-orphan")


class AgentSkill(Base):
    """Agent 与技能关联"""
    __tablename__ = "agent_skills"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sub_agents.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    proficiency: Mapped[int] = mapped_column(Integer, default=5)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    agent = relationship("SubAgent", back_populates="skills")
    skill = relationship("Skill", back_populates="agents")
