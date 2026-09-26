"""工作日历 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkCalendarCreate(BaseModel):
    name: str
    work_days: str = "1,2,3,4,5"
    work_start: str = "09:00"
    work_end: str = "18:00"
    holidays: str | None = None


class WorkCalendarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    work_days: str
    work_start: str
    work_end: str
    holidays: str | None = None
    created_at: datetime | None = None
