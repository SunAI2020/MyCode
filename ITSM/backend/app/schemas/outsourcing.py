"""外包协作 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---- 外包人员 ----
class OutsourceUserCreate(BaseModel):
    name: str
    org: str | None = None
    qualification: str | None = None
    settle_type: str = "按次"
    permissions: str | None = None


class OutsourceUserUpdate(BaseModel):
    name: str | None = None
    org: str | None = None
    qualification: str | None = None
    settle_type: str | None = None
    permissions: str | None = None


class OutsourceUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    org: str | None = None
    qualification: str | None = None
    settle_type: str
    permissions: str | None = None
    created_at: datetime | None = None


# ---- 外包任务 ----
class OutsourcingCreate(BaseModel):
    work_order_id: int
    type: str = "能力"
    outsource_user_id: int
    price: float | None = None
    nda: str | None = None
    status: str = "待接单"


class OutsourcingUpdate(BaseModel):
    type: str | None = None
    outsource_user_id: int | None = None
    price: float | None = None
    nda: str | None = None


class OutsourcingStatusUpdate(BaseModel):
    status: str


class OutsourcingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    type: str
    outsource_user_id: int
    price: float | None = None
    nda: str | None = None
    status: str
    created_at: datetime | None = None


# ---- 外包汇报 ----
class OutsourcingReportCreate(BaseModel):
    outsourcing_id: int
    report_date: date
    progress: str | None = None
    attachments: str | None = None
    acceptance: str | None = None


class OutsourcingReportUpdate(BaseModel):
    report_date: date | None = None
    progress: str | None = None
    attachments: str | None = None
    acceptance: str | None = None


class OutsourcingReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    outsourcing_id: int
    report_date: date
    progress: str | None = None
    attachments: str | None = None
    acceptance: str | None = None
    created_at: datetime | None = None
