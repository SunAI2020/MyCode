"""接单 / 工单 / 派单 / 执行人 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- 接单 ----
class OrderReceiveCreate(BaseModel):
    source: str = "客户报障"
    customer_id: int
    contract_id: int | None = None
    contract_item_id: int | None = None
    ci_id: int | None = None
    project: str | None = None
    contract_price: float | None = None
    contact: str | None = None
    service_start: date | None = None
    service_end: date | None = None
    accept_standard: str | None = None


class OrderReceiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    customer_id: int
    contract_id: int | None = None
    contract_item_id: int | None = None
    ci_id: int | None = None
    project: str | None = None
    contract_price: float | None = None
    contact: str | None = None
    service_start: date | None = None
    service_end: date | None = None
    accept_standard: str | None = None
    created_at: datetime | None = None


# ---- 工单 ----
class WorkOrderCreate(BaseModel):
    receive_id: int | None = None
    type: str = "客户工单"
    contract_id: int | None = None
    contract_item_id: int | None = None
    ci_id: int | None = None
    project: str | None = None
    priority: str = "中"
    description: str | None = None
    task_type: str | None = None  # 内部任务类型
    deadline: datetime | None = None  # 内部任务截止时间


class WorkOrderStatusUpdate(BaseModel):
    status: str
    progress: int | None = Field(None, ge=0, le=100)


class WorkOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    no: str
    type: str
    customer_id: int | None = None
    receive_id: int | None = None
    dispatch_id: int | None = None
    contract_id: int | None = None
    contract_item_id: int | None = None
    ci_id: int | None = None
    project: str | None = None
    description: str | None = None
    task_type: str | None = None
    deadline: datetime | None = None
    status: str
    priority: str
    sla_deadline: datetime | None = None
    progress: int
    current_cycle_no: int | None = None
    created_at: datetime | None = None
    assignee_names: list[str] = []  # 执行人姓名（列表接口 enrich，便于直接展示）


# ---- 工单聚合 ----
class AggregateCycleIn(BaseModel):
    contract_item_id: int
    cycle_no: int


class AggregatePreviewIn(BaseModel):
    contract_item_ids: list[int]


class AggregateWorkOrderCreate(BaseModel):
    customer_id: int
    ci_ids: list[int] = []
    contract_item_ids: list[int] = []
    cycles: list[AggregateCycleIn] = []
    type: str = "客户工单"
    priority: str = "中"
    description: str | None = None


# ---- 派单 / 执行人 ----
class AssigneeIn(BaseModel):
    user_id: int
    workload_ratio: float = 100


class TransferIn(BaseModel):
    from_user_id: int
    to_user_id: int
    actual_hours: float | None = None


class AssigneeHoursIn(BaseModel):
    actual_hours: float
    complete: bool = False  # 完成则离岗（is_active=False）


class DispatchCreate(BaseModel):
    dispatch_type: str = "内部"
    dispatch_price: float | None = None
    service_start: date | None = None
    service_end: date | None = None
    accept_standard: str | None = None
    suggest_reason: str | None = None
    assignees: list[AssigneeIn]


class AssigneeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    user_id: int
    workload_ratio: float
    actual_hours: float | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    is_active: bool


class DispatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    dispatch_type: str
    dispatch_price: float | None = None
    service_start: date | None = None
    service_end: date | None = None
    accept_standard: str | None = None
    suggest_reason: str | None = None
    created_at: datetime | None = None
