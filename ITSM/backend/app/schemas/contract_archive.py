"""合同原件档案 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ServiceItemIn(BaseModel):
    project: str
    frequency: int = 1
    unit: str = "月"
    price: float | None = None
    service_object: str | None = None  # 关联业务系统名（可空，空则归首个业务系统）


class ContractArchiveConfirm(BaseModel):
    """确认导入：编辑后的抽取字段 + 可选显式客户。"""

    customer_id: int | None = None  # 显式选择已有客户（优先）
    contract_id: int | None = None  # 挂到已有项目（优先于新建项目）；为空则新建 客户→项目→业务系统→服务类别
    name: str | None = None  # 合同名称
    customer_name: str | None = None
    contract_no: str | None = None
    sign_date: str | None = None  # YYYY-MM-DD
    amount: float | None = None
    has_onsite: bool | None = None
    service_period: str | None = None
    service_location: str | None = None
    staff_requirement: str | None = None
    accept_standard: str | None = None
    delivery_docs: str | None = None
    acceptance_report_format: str | None = None
    service_objects: list[str] = []
    service_items: list[ServiceItemIn] = []


class ContractArchiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int | None = None
    customer_id: int | None = None
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    created_at: datetime | None = None
