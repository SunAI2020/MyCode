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
    created_at: datetime | None = None


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
    ci_id: int
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
