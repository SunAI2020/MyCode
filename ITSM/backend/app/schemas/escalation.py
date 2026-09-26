"""SLA 升级记录 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int | None = None
    level: str
    from_user: str | None = None
    to_user: str | None = None
    triggered_at: datetime | None = None
    reason: str | None = None
