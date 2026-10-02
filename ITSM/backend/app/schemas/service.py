"""SLA 策略 / 服务周期 / 服务提醒 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class SlaPolicyCreate(BaseModel):
    name: str
    customer_level: str | None = None
    response_limit: str | None = None
    resolve_limit: str | None = None
    work_calendar_id: int | None = None
    escalation_chain: str | None = None


class SlaPolicyUpdate(BaseModel):
    name: str | None = None
    customer_level: str | None = None
    response_limit: str | None = None
    resolve_limit: str | None = None
    work_calendar_id: int | None = None
    escalation_chain: str | None = None


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    customer_level: str | None = None
    response_limit: str | None = None
    resolve_limit: str | None = None
    work_calendar_id: int | None = None
    escalation_chain: str | None = None


class ServiceCycleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_item_id: int
    cycle_no: int
    service_start: date
    service_end: date
    status: str
    auto_generated: bool
    created_at: datetime | None = None
    # 富化字段（列表接口填充，便于直接展示）
    customer_name: str | None = None  # 客户名称
    project_name: str | None = None  # 项目名称（合同名）
    ci_name: str | None = None  # 业务系统
    item_project: str | None = None  # 服务类别


class ServiceCycleUpdate(BaseModel):
    service_start: date | None = None
    service_end: date | None = None
    status: str | None = None


class ServiceReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_id: int | None = None
    type: str
    level: str
    content: str
    to_user_id: int | None = None
    channel: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None
