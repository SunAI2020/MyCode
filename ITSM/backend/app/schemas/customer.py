"""客户 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    name: str
    short_name: str | None = None
    industry: str | None = None
    level: str = "普通"  # 金牌/银牌/普通
    contact: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    industry: str | None = None
    level: str | None = None
    contact: str | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str | None = None
    industry: str | None = None
    level: str
    contact: str | None = None
    created_at: datetime | None = None
