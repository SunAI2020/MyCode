"""驻场服务 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---- 驻场配置 ----
class OnsiteServiceCreate(BaseModel):
    contract_id: int
    customer_id: int
    headcount: int = 1
    period_start: date | None = None
    period_end: date | None = None
    work_items: str | None = None
    status: str = "执行中"


class OnsiteServiceUpdate(BaseModel):
    contract_id: int | None = None
    customer_id: int | None = None
    headcount: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    work_items: str | None = None
    status: str | None = None


class OnsiteServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    customer_id: int
    headcount: int
    period_start: date | None = None
    period_end: date | None = None
    work_items: str | None = None
    status: str
    created_at: datetime | None = None


# ---- 驻场日报 ----
class OnsiteDailyReportCreate(BaseModel):
    onsite_id: int
    report_date: date
    work_type: str
    content: str
    issue_ref: int | None = None
    # 不暴露 user_id：作者一律取当前登录用户（防 mass-assignment 冒名）


class OnsiteDailyReportUpdate(BaseModel):
    report_date: date | None = None
    work_type: str | None = None
    content: str | None = None
    issue_ref: int | None = None


class OnsiteDailyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    onsite_id: int
    user_id: int
    report_date: date
    work_type: str
    content: str
    issue_ref: int | None = None
    created_at: datetime | None = None


# ---- 驻场人员清单 ----
class OnsiteAssignmentCreate(BaseModel):
    onsite_id: int
    user_id: int
    start_date: date | None = None
    end_date: date | None = None
    status: str = "在岗"  # 在岗/离岗


class OnsiteAssignmentUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None


class OnsiteAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    onsite_id: int
    user_id: int
    start_date: date | None = None
    end_date: date | None = None
    status: str
    created_at: datetime | None = None
