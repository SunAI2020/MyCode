"""知识库 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KbArticleCreate(BaseModel):
    title: str
    category: str = "故障手册"
    content: str
    tags: str | None = None
    status: str = "已发布"


class KbArticleUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    tags: str | None = None
    status: str | None = None


class KbArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    content: str
    tags: str | None = None
    status: str
    author_id: int | None = None
    view_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
