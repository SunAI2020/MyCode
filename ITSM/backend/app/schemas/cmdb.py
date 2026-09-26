"""CMDB 依赖拓扑 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CmdbCiDependencyCreate(BaseModel):
    source_ci_id: int
    target_ci_id: int
    relation: str = "依赖"


class CmdbCiDependencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_ci_id: int
    target_ci_id: int
    relation: str
    created_at: datetime | None = None
