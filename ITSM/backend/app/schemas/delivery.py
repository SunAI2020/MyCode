"""项目交付 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeliveryCreate(BaseModel):
    work_order_id: int | None = None
    contract_id: int | None = None
    contract_item_id: int | None = None
    title: str
    report_type: str = "运维报告"
    report_id: str | None = None


class DeliveryUpdate(BaseModel):
    work_order_id: int | None = None
    contract_id: int | None = None
    contract_item_id: int | None = None
    title: str | None = None
    report_type: str | None = None
    report_id: str | None = None
    sign: str | None = None


class DeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int | None = None
    contract_id: int | None = None
    contract_item_id: int | None = None
    title: str
    report_type: str
    report_id: str | None = None
    sign: str
    created_at: datetime | None = None
    # 富化字段（列表接口填充）
    customer_name: str | None = None
    project_name: str | None = None
    work_order_no: str | None = None
