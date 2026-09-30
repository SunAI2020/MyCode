"""合规运营框架 schema（步骤 51）。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


# ---- 合规要求 ----
class ComplianceRequirementCreate(BaseModel):
    customer_id: int
    project_id: int | None = None
    source_type: str = "监管"  # 监管/合同义务/服务项目
    source_id: int | None = None
    clause: str
    category: str = "技术"  # 技术/组织/制度/台账/流程
    reg_source: str | None = None
    status: str = "启用"


class ComplianceRequirementUpdate(BaseModel):
    project_id: int | None = None
    source_type: str | None = None
    source_id: int | None = None
    clause: str | None = None
    category: str | None = None
    reg_source: str | None = None
    status: str | None = None


class ComplianceRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    project_id: int | None = None
    source_type: str
    source_id: int | None = None
    clause: str
    category: str
    reg_source: str | None = None
    status: str
    created_at: datetime | None = None


# ---- 合规证据 ----
class ComplianceEvidenceCreate(BaseModel):
    requirement_id: int
    source_type: str = "人工"  # 工单/整改/变更/交付/审批/审计/人工
    source_id: int | None = None
    evidence_type: str = "人工"  # 自动/人工
    file_ref: str | None = None
    content_hash: str | None = None
    note: str | None = None


class ComplianceEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requirement_id: int
    source_type: str
    source_id: int | None = None
    evidence_type: str
    file_ref: str | None = None
    content_hash: str | None = None
    operator_id: int | None = None
    occurred_at: datetime | None = None
    note: str | None = None
    created_at: datetime | None = None


# ---- 合规核验 ----
class ComplianceCheckCreate(BaseModel):
    requirement_id: int
    check_type: str = "巡查"  # 巡查/自查/攻防校验/复测
    assignee: int | None = None
    check_date: date | None = None
    note: str | None = None


class ComplianceCheckUpdate(BaseModel):
    check_type: str | None = None
    result: str | None = None  # 通过/不通过/部分（status 由状态机派生，不可直接设）
    evidence_id: int | None = None
    assignee: int | None = None
    check_date: date | None = None
    note: str | None = None


class ComplianceCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requirement_id: int
    check_type: str
    status: str
    result: str | None = None
    issue_id: int | None = None
    evidence_id: int | None = None
    assignee: int | None = None
    check_date: date | None = None
    note: str | None = None
    created_at: datetime | None = None


# ---- 履职报告 ----
class DutyReportCreate(BaseModel):
    customer_id: int
    project_id: int | None = None
    period_start: date | None = None
    period_end: date | None = None


class DutyReportUpdate(BaseModel):
    status: str | None = None
    content_json: str | None = None
    file_ref: str | None = None
    sign: str | None = None


class DutyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    project_id: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    status: str
    content_json: str | None = None
    file_ref: str | None = None
    sign: str
    created_by: int | None = None
    created_at: datetime | None = None


# ---- 监管要求模板 ----
class ComplianceTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reg_source: str
    domain: str
    title: str
    clause: str
    category: str


class TemplateApplyIn(BaseModel):
    customer_id: int
    project_id: int | None = None
