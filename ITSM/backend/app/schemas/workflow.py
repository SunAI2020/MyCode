"""工作流规则 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowRuleCreate(BaseModel):
    entity: str = Field(..., description="work_order/change_order/outsourcing")
    from_status: str
    to_status: str
    name: str | None = None
    auto_action: str | None = None
    enabled: bool = True


class WorkflowRuleUpdate(BaseModel):
    from_status: str | None = None
    to_status: str | None = None
    name: str | None = None
    auto_action: str | None = None
    enabled: bool | None = None


class WorkflowRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity: str
    from_status: str
    to_status: str
    name: str | None = None
    auto_action: str | None = None
    enabled: bool
    created_at: datetime | None = None
