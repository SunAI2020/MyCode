"""变更单 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChangeOrderCreate(BaseModel):
    work_order_id: int | None = None
    ci_id: int
    risk_level: str = "中"
    rollback_plan: str | None = None
    status: str = "草稿"


class ChangeOrderUpdate(BaseModel):
    work_order_id: int | None = None
    ci_id: int | None = None
    risk_level: str | None = None
    rollback_plan: str | None = None


class ChangeOrderStatusUpdate(BaseModel):
    status: str


class ChangeOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int | None = None
    ci_id: int
    risk_level: str
    conflict_flag: bool
    rollback_plan: str | None = None
    status: str
    created_at: datetime | None = None
