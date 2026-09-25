"""问题整改 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class IssueCreate(BaseModel):
    type: str = "安全漏洞"
    level: str = "中"
    description: str
    attachments: str | None = None
    similar_ids: str | None = None


class IssueUpdate(BaseModel):
    type: str | None = None
    level: str | None = None
    description: str | None = None
    attachments: str | None = None
    similar_ids: str | None = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    type: str
    level: str
    description: str
    attachments: str | None = None
    similar_ids: str | None = None
    status: str
    created_at: datetime | None = None


class RectificationCreate(BaseModel):
    plan: str
    deadline: date | None = None
    assignee: int | None = None


class RectificationUpdate(BaseModel):
    plan: str | None = None
    deadline: date | None = None
    assignee: int | None = None


class RectificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    plan: str
    deadline: date | None = None
    assignee: int | None = None
    status: str
    created_at: datetime | None = None


class RoundIn(BaseModel):
    action: str
    executor: int | None = None
    effect: str  # 通过/不通过/部分完成


class RectificationRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rectification_id: int
    round_no: int
    action: str
    executor: int | None = None
    effect: str
    created_at: datetime | None = None
