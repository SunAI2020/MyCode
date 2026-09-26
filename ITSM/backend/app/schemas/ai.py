"""AI 增强 / 技能矩阵 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClassifyIn(BaseModel):
    description: str


class ClassifyOut(BaseModel):
    project: str
    priority: str


class EngineerSkillCreate(BaseModel):
    user_id: int
    skill: str
    level: str = "中级"  # 初级/中级/高级


class EngineerSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    skill: str
    level: str
    created_at: datetime | None = None
