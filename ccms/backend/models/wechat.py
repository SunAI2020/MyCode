# -*- coding: utf-8 -*-
"""微信相关模型"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class WeChatUser(Base, UUIDMixin, TimestampMixin):
    """微信用户绑定"""
    __tablename__ = "wechat_users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    openid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    unionid: Mapped[str | None] = mapped_column(String(128), index=True)
    mp_openid: Mapped[str | None] = mapped_column(String(128))
    nickname: Mapped[str | None] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    phone: Mapped[str | None] = mapped_column(String(20))
    session_key: Mapped[str | None] = mapped_column(String(255))  # 加密存储
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    push_agent_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    push_agent_error: Mapped[bool] = mapped_column(Boolean, default=True)
    push_token_alert: Mapped[bool] = mapped_column(Boolean, default=True)
    push_daily_report: Mapped[bool] = mapped_column(Boolean, default=False)
    push_weekly_report: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_purpose: Mapped[str | None] = mapped_column(String(255))
    consent_version: Mapped[str | None] = mapped_column(String(32))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WeChatMessage(Base, UUIDMixin):
    """微信消息记录"""
    __tablename__ = "wechat_messages"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    openid: Mapped[str | None] = mapped_column(String(128))
    msg_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WeChatNotification(Base, UUIDMixin):
    """微信推送记录"""
    __tablename__ = "wechat_notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    template_id: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
