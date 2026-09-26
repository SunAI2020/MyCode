"""审批流 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApprovalCreate(BaseModel):
    entity: str  # work_order / change_order / outsourcing
    entity_id: int
    to_status: str
    reason: str | None = None


class ApprovalDecision(BaseModel):
    note: str | None = None


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity: str
    entity_id: int
    from_status: str
    to_status: str
    applicant_id: int
    approver_id: int | None = None
    status: str
    reason: str | None = None
    decision_note: str | None = None
    created_at: datetime | None = None
    decided_at: datetime | None = None
