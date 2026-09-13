# -*- coding: utf-8 -*-
"""系统指标模型"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MetricSnapshot(Base):
    """系统指标快照（按月分区）"""
    __tablename__ = "metric_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    node_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True))
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    labels: Mapped[dict] = mapped_column(JSONB, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
