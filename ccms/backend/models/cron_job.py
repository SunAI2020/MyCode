# -*- coding: utf-8 -*-
"""定时任务模型"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class CronJob(Base, UUIDMixin, TimestampMixin):
    """定时任务定义"""
    __tablename__ = "cron_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    max_runs: Mapped[int | None] = mapped_column(Integer)


class CronExecution(Base, UUIDMixin):
    """定时任务执行记录"""
    __tablename__ = "cron_executions"

    cron_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cron_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="running", server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
