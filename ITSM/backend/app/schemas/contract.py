"""合同 / 服务对象(CI) / 合同子项 schema。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---- 合同 ----
class ContractCreate(BaseModel):
    customer_id: int
    type: str = "安全服务"
    name: str
    no: str | None = None
    amount: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    has_onsite: bool = False
    status: str = "洽谈中"
    sign_date: date | None = None
    staff_requirement: str | None = None
    accept_standard: str | None = None
    delivery_docs: str | None = None
    acceptance_report_format: str | None = None
    service_location: str | None = None


class ContractUpdate(BaseModel):
    customer_id: int | None = None
    type: str | None = None
    name: str | None = None
    no: str | None = None
    amount: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    has_onsite: bool | None = None
    status: str | None = None
    sign_date: date | None = None
    staff_requirement: str | None = None
    accept_standard: str | None = None
    delivery_docs: str | None = None
    acceptance_report_format: str | None = None
    service_location: str | None = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    type: str
    name: str
    no: str | None = None
    amount: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    has_onsite: bool
    status: str
    sign_date: date | None = None
    staff_requirement: str | None = None
    accept_standard: str | None = None
    delivery_docs: str | None = None
    acceptance_report_format: str | None = None
    service_location: str | None = None
    created_at: datetime | None = None
    archive_count: int = 0  # 归档的合同原件数量（列表接口填充，供前端灰显无原件项目）


# ---- 服务对象 CI ----
class CmdbCiCreate(BaseModel):
    contract_id: int
    name: str
    type: str = "业务系统"
    ip: str | None = None
    status: str = "在用"
    version: str | None = None
    lifecycle: str = "在用"


class CmdbCiUpdate(BaseModel):
    contract_id: int | None = None
    name: str | None = None
    type: str | None = None
    ip: str | None = None
    status: str | None = None
    version: str | None = None
    lifecycle: str | None = None


class CmdbCiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    contract_id: int
    name: str
    type: str
    ip: str | None = None
    status: str
    version: str | None = None
    lifecycle: str
    created_at: datetime | None = None


# ---- 合同子项 ----
class ContractItemCreate(BaseModel):
    ci_id: int | None = None  # 关联服务目标；None = 不针对具体系统（记作「//」）
    contract_id: int | None = None  # ci_id 为空时需显式指定所属项目
    project: str
    frequency: int = 1
    unit: str = "月"
    sla_policy_id: int | None = None
    accept_standard: str | None = None
    price: float | None = None


class ContractItemUpdate(BaseModel):
    ci_id: int | None = None
    project: str | None = None
    frequency: int | None = None
    unit: str | None = None
    sla_policy_id: int | None = None
    accept_standard: str | None = None
    price: float | None = None


class ContractItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    ci_id: int | None = None
    project: str
    frequency: int
    unit: str
    sla_policy_id: int | None = None
    accept_standard: str | None = None
    price: float | None = None
    created_at: datetime | None = None
